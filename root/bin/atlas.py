import requests
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException, TooManyRedirects
import os


def main(args: list):
    print(os.getcwd())
    print(args)