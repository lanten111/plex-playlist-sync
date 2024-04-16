import logging
import os
import time
import traceback

import deezer
import spotipy
from jellyfin_api_client import AuthenticatedClient
from jellyfinapi.jellyfinapi_client import JellyfinapiClient
from plexapi.server import PlexServer
from spotipy.oauth2 import SpotifyClientCredentials
from ytmusicapi import YTMusic

from utils.deezer import deezer_playlist_sync
from utils.helperClasses import UserInputs
from utils.spotify import spotify_playlist_sync
from utils.ytmusic import ytmusic_playlist_sync

# Read ENV variables
userInputs = UserInputs(
    plex_url=os.getenv("PLEX_URL"),
    plex_token=os.getenv("PLEX_TOKEN"),
    write_missing_as_csv=os.getenv("WRITE_MISSING_AS_CSV", "0") == "1",
    append_service_suffix=os.getenv("APPEND_SERVICE_SUFFIX", "1") == "1",
    add_playlist_poster=os.getenv("ADD_PLAYLIST_POSTER", "1") == "1",
    add_playlist_description=os.getenv("ADD_PLAYLIST_DESCRIPTION", "1") == "1",
    append_instead_of_sync=os.getenv("APPEND_INSTEAD_OF_SYNC", False) == "1",
    wait_seconds=int(os.getenv("SECONDS_TO_WAIT", 86400)),
    spotipy_client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    spotipy_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    spotify_user_id=os.getenv("SPOTIFY_USER_ID"),
    deezer_user_id=os.getenv("DEEZER_USER_ID"),
    deezer_playlist_ids=os.getenv("DEEZER_PLAYLIST_ID"),
    jellyfin_url=os.getenv("JELLYFIN_URL", "http://192.168.1.5:8096"),
    jellyfin_token=os.getenv("JELLYFIN_TOKEN", "7cf21b149808479fa87a5836ea498d9d"),
    jellyfin_user=os.getenv("JELLYFIN_USER", "muhumbulo"),
)
while True:
    logging.info("Starting playlist sync")


    ########## PLEX MUSIC SYNC ##########

    PL_AUTHSUCCESS = False
    if userInputs.plex_url and userInputs.plex_token:
        try:
            plex = PlexServer(userInputs.plex_url, userInputs.plex_token)
            PL_AUTHSUCCESS = True
        except:
            logging.error("Plex Authorization error")
    else:
        logging.error("Missing Plex Authorization Variables")

    ########## JELLYFIN MUSIC SYNC ##########

    JL_AUTHSUCCESS = False
    if userInputs.jellyfin_url and userInputs.jellyfin_token:
        try:
            jellyfin = JellyfinapiClient(x_emby_token=userInputs.jellyfin_token, server_url=userInputs.jellyfin_url)
            JL_AUTHSUCCESS = True
        except:
            logging.error(traceback.format_exc())
    else:
        logging.error("Missing Plex Authorization Variables")


    ########## YT MUSIC SYNC ##########

    logging.info("Starting youtube music playlist sync")

    YT_AUTHSUCCESS = False

    authfile = r"C:\Users\Muhumbulo\PycharmProjects\plex-playlist-sync\plex-playlist-sync\config\oauth.json"
    if (
            os.path.exists(authfile)
    ):
        try:
            yt = ytmusic = YTMusic(authfile)
            YT_AUTHSUCCESS = True
        except:
            logging.info("youtube Authorization error, skipping spotify sync")

    else:
        logging.info(
            "Missing one or more youtube Authorization Variables, skipping"
            " youtube sync"
        )

    if YT_AUTHSUCCESS:
        if PL_AUTHSUCCESS and JL_AUTHSUCCESS:
            ytmusic_playlist_sync(yt, plex, jellyfin, userInputs)
        elif PL_AUTHSUCCESS and JL_AUTHSUCCESS is False:
            ytmusic_playlist_sync(yt, plex, None, userInputs)
        elif JL_AUTHSUCCESS and PL_AUTHSUCCESS is False:
            ytmusic_playlist_sync(yt, None, jellyfin, userInputs)
        else:
            logging.error("Plex or jellyfin auth must be present")
            break

    logging.info("Spotify playlist sync complete")


    ########## SPOTIFY SYNC ##########

    logging.info("Starting ytmusic playlist sync")

    SP_AUTHSUCCESS = False

    if (
        userInputs.spotipy_client_id
        and userInputs.spotipy_client_secret
        and userInputs.spotify_user_id
    ):
        try:
            sp = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    userInputs.spotipy_client_id,
                    userInputs.spotipy_client_secret,
                )
            )
            SP_AUTHSUCCESS = True
        except:
            logging.info("Spotify Authorization error, skipping spotify sync")

    else:
        logging.info(
            "Missing one or more Spotify Authorization Variables, skipping"
            " spotify sync"
        )

    if SP_AUTHSUCCESS:
        spotify_playlist_sync(sp, plex, userInputs)

    logging.info("Spotify playlist sync complete")

    ########## DEEZER SYNC ##########

    logging.info("Starting Deezer playlist sync")
    dz = deezer.Client()
    deezer_playlist_sync(dz, plex, userInputs)
    logging.info("Deezer playlist sync complete")

    logging.info("All playlist(s) sync complete")
    logging.info("sleeping for %s seconds" % userInputs.wait_seconds)

    time.sleep(userInputs.wait_seconds)
