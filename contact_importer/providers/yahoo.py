# -*- coding: utf-8 -*-
""" Yahoo Contact Importer module """

from .base import BaseProvider
from ..lib import oauth1 as oauth
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode
try:
    from urlparse import parse_qs
except ImportError:
    from urllib.parse import parse_qs
from uuid import uuid4 as uuid
from collections import OrderedDict
from time import time
from hashlib import md5
import requests
import json


REQUEST_TOKEN_URL = "https://api.login.yahoo.com/oauth/v2/get_request_token"
REQUEST_AUTH_URL = "https://api.login.yahoo.com/oauth/v2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth/v2/get_token"
CONTACTS_URL = "https://social.yahooapis.com/v1/user/%s/contacts"


class YahooContactImporter(BaseProvider):

    def __init__(self, *args, **kwargs):
        super(YahooContactImporter, self).__init__(*args, **kwargs)
        self.request_token_url = REQUEST_TOKEN_URL
        self.request_auth_url = REQUEST_AUTH_URL
        self.token_url = TOKEN_URL
        self.oauth_timestamp = int(time())
        self.oauth_nonce = md5("%s%s" % (uuid(), self.oauth_timestamp)).hexdigest()

    def get_request_token(self):
        request_params = dict(
            oauth_consumer_key=self.client_id,
            oauth_nonce=self.oauth_nonce,
            oauth_signature_method="plaintext",
            oauth_signature=self.client_secret + "&",
            oauth_timestamp=self.oauth_timestamp,
            oauth_version="1.0",
            oauth_callback=self.redirect_url
        )

        request_url = "%s?%s" % (self.request_token_url, urlencode(request_params))
        response = requests.post(request_url)
        query_string = parse_qs(response.text)
        self.oauth_token = query_string["oauth_token"][0]
        self.oauth_token_secret = query_string["oauth_token_secret"][0]

    def request_authorization(self):
        request_params = dict(oauth_token=self.oauth_token)
        return "%s?%s" % (self.request_auth_url, urlencode(request_params))

    def get_token(self):
        request_params = dict(
            oauth_consumer_key=self.client_id,
            oauth_signature_method="plaintext",
            oauth_nonce=self.oauth_nonce,
            oauth_signature=self.client_secret + "&" + self.oauth_token_secret,
            oauth_timestamp=self.oauth_timestamp,
            oauth_verifier=self.oauth_verifier,
            oauth_version="1.0",
            oauth_token=self.oauth_token
        )
        request_url = "%s?%s" % (self.token_url, urlencode(request_params))
        response = requests.post(request_url)
        response_query = parse_qs(response.text)
        
        self.oauth_token = response_query["oauth_token"][0]
        self.oauth_token_secret = response_query["oauth_token_secret"][0]
        self.oauth_yahoo_guid = response_query["xoauth_yahoo_guid"][0]

    def import_contacts(self):
        request_url = CONTACTS_URL % self.oauth_yahoo_guid

        request_params = dict(
            oauth_consumer_key=self.client_id,
            oauth_nonce=self.oauth_nonce,
            oauth_signature_method="HMAC-SHA1",
            oauth_timestamp=str(self.oauth_timestamp),
            oauth_token=self.oauth_token,
            oauth_version="1.0",
            count="max",
            format="json"
        )

        request_params_new = OrderedDict(sorted(request_params.items(), key=lambda t: t[0]))

        consumer = oauth.OAuthConsumer(key=self.client_id, secret=self.client_secret)
        token = oauth.OAuthToken(key=self.oauth_token, secret=self.oauth_token_secret)
        request = oauth.OAuthRequest(http_method="GET", http_url=request_url, parameters=request_params)
        signature = request.build_signature(oauth.OAuthSignatureMethod_HMAC_SHA1(), consumer, token)

        request_params_new['oauth_signature'] = signature
        request_params_new['count'] = "max"
        request_params_new['format'] = "json"

        response = requests.get(request_url, params=request_params_new)
        return self.parse_contacts(response.text)

    def parse_contacts(self, contacts_json):
        contacts = json.loads(contacts_json)
        contacts_list = []

        for contact in contacts['contacts']['contact']:
            contact_type = contact['fields'][0]['type']
            contact_value = contact['fields'][0]['value']

            if contact_type == "name":
                continue

            if contact_type == "yahooid" and not "@" in contact_value:
                contact_value += "@yahoo.com"
            
            contacts_list.append(contact_value)

        return contacts_list


