#!/usr/bin/env python
#
# Copyright 2011 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Starting template for Google App Engine applications.

Use this project as a starting point if you are just beginning to build a Google
App Engine project. Remember to fill in the OAuth 2.0 client_id and
client_secret which can be obtained from the Developer Console
<https://code.google.com/apis/console/>
"""

__author__ = 'Wolff Dobson'

import settings
import cgi
import httplib2
import logging
import os
import pickle
import urllib
import simplejson as json
import re

from apiclient.discovery import build
from oauth2client.appengine import OAuth2Decorator

from google.appengine.api import memcache, users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app, login_required
from google.appengine.ext.webapp import template

import gdata.gauth
import gdata.docs.client
import gdata.youtube
import gdata.youtube.client
import gdata.alt.appengine

import gdata.photos.service
import gdata.media
import gdata.geo
import gdata.calendar.client


USER_AGENT=""

#gdocs = gdata.docs.client.DocsClient(source = "gplustimeline")
clients = {}
clients["youtube"] = gdata.youtube.client.YouTubeClient()
#gdata.alt.appengine.run_on_appengine(clients["youtube"])

clients["picasa"] = gdata.photos.service.PhotosService()
#gdata.alt.appengine.run_on_appengine(clients["picasa"])

clients["calendar"] = gdata.calendar.client.CalendarClient(source="")
#gdata.alt.appengine.run_on_appengine(clients["calendar"])


# The client_id and client_secret are copied from the API Access tab on
# the Google APIs Console <http://code.google.com/apis/console>
decorator = OAuth2Decorator(
    client_id=settings.CLIENT_ID,
    client_secret=settings.CLIENT_SECRET,
    scope = 'https://www.googleapis.com/auth/plus.me https://picasaweb.google.com/data/ http://gdata.youtube.com https://docs.google.com/feeds/ https://www.google.com/calendar/feeds/')

http = httplib2.Http(memcache)
httpUnauth = httplib2.Http(memcache)

# Get discovery document
ul = urllib.urlopen(settings.DISCOVERY_DOCUMENT)
discovery_doc = ul.read()
ul.close()

service = build("plus", "v1", http=http)

serviceUnauth = build("plus", "v1", http=http, developerKey=settings.API_KEY)


class WelcomeHandler(webapp.RequestHandler):
    def get(self):

        path = os.path.join(os.path.dirname(__file__), 'index.html')

        self.response.out.write(
            template.render(path, {}))

        #self.redirect(self.request.body + '/play')

class PlayHandler(webapp.RequestHandler):
    @decorator.oauth_aware
    def get(self):

        if (not decorator.has_credentials()):
            self.redirect(self.request.body + '/login')
            return

        http = decorator.http()
        people = service.people().get(userId='me').execute(http)
        import pprint

        logging.info(pprint.pformat(people))
        path = os.path.join(os.path.dirname(__file__), 'play.html')

        me = service.people().get(userId='me').execute(decorator.http())

        # Now I have my own id, I can do things unauth'd
        # I could continue using my authenticated service,
        # but for example we'll use a second unauth'd one.
        activities_doc = service.activities().list(userId=me['id'], collection='public').execute(http)

        activities = []
        if 'items' in activities_doc:
            activities += activities_doc['items']

        top_activity_content = "No top activity content"

        if len(activities) > 0:
            activities_doc = serviceUnauth.activities().get(activityId=activities[0]['id']).execute(httpUnauth)

            top_activity_content = activities_doc['object']['content']

        creds = decorator.credentials.to_json()
        logging.info(decorator.credentials.to_json())
        
        # "token_expiry": "2011-09-29T19:59:53Z"

        token = gdata.gauth.OAuth2Token(client_id=settings.CLIENT_ID, client_secret=settings.CLIENT_SECRET, scope=decorator.flow.scope,
   user_agent=USER_AGENT, access_token=decorator.credentials.access_token,token_uri=decorator.credentials.token_uri,refresh_token=decorator.credentials.refresh_token)


        clients["calendar"] = token.authorize(clients["calendar"])
        clients["youtube"] = token.authorize(clients["youtube"])
        clients["picasa"] = token.authorize(clients["picasa"])
                

        #youtube
        feed = clients["youtube"].get_user_feed(username="sylvinus") #GetYouTubeUserFeed("sylvinus")
        #todo reformat
        for entry in feed.entry:

            activities.append({
                "kind":"youtube#video",
                "title":entry.title.text,
                "verb":"global_featured",
                "youtube_player":re.sub(".*video\:","",entry.get_id()), ##todo !!
                "published":entry.published.text
            })
        


        feed = clients["calendar"].get_calendar_event_feed()
        for entry in feed.entry:
            activities.append({
                "kind":"calendar#event",
                "title":entry.title.text,
                "published":entry.when[0].start
            })
        


        self.response.out.write(
            template.render(path, {'me': me, 'me_json': json.dumps(me), 'activities': json.dumps(activities),
                                   'top_activity_content': json.dumps(top_activity_content)}))

class LoginHandler(webapp.RequestHandler):
    @decorator.oauth_aware
    def get(self):
        if ( decorator.has_credentials() ):
            self.redirect(self.request.body + '/play')
            return

        path = os.path.join(os.path.dirname(__file__), 'login.html')

        self.response.out.write(
            template.render(path, {}))

        return

    @decorator.oauth_required
    def post(self):
        self.redirect(self.request.body + '/play')

def main():
  application = webapp.WSGIApplication(
      [
      ('/', WelcomeHandler),
       ('/play', PlayHandler),
       ('/login', LoginHandler),
      ],
      debug=True)
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
