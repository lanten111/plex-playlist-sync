import logging
from typing import List

import spotipy
from plexapi.server import PlexServer

from .helperClasses import Playlist, Track, UserInputs
from .plex import update_or_create_plex_playlist
from .jellyfin import update_or_create_jellyfin_playlist


def _get_yt_user_playlists(yt) -> List[Playlist]:

    playlists = []

    try:
        yt_playlists = yt.get_library_playlists()
        for playlist in yt_playlists:
            playlists.append(
                Playlist(
                    id=playlist["playlistId"],
                    name=playlist["title"],
                    description=playlist.get("description", ""),
                    # playlists may not have a poster in such cases return ""
                    poster=""
                    # if len(playlist["images"]) == 0
                    # else playlist["images"][0].get("url", ""),
                )
            )
    except:
        logging.error("Spotify User ID Error")
    return playlists


def _get_yt_tracks_from_playlist(yt, playlist: Playlist) -> List[Track]:

    def extract_sp_track_metadata(track) -> Track:
        title = track["title"]
        artist = track["artists"][0]["name"]
        if track["album"] is not None:
            album = track["album"]["name"]
        else:
            album = ""
        url = ""
        return Track(title, artist, album, url)

    # return all tracks in a playlist
    yt_playlist_tracks = yt.get_playlist(playlist.id, None)

    tracks = list(
        map(
            extract_sp_track_metadata,
            [i for i in yt_playlist_tracks['tracks'] if i.get("title")],
        )
    )
    return tracks


def ytmusic_playlist_sync(yt, plex, jellyfin, userInputs) -> None:
    playlists = _get_yt_user_playlists(yt)
    if playlists:
        for playlist in playlists:
            tracks = _get_yt_tracks_from_playlist(yt, playlist)
            if plex is not None:
                update_or_create_plex_playlist(plex, playlist, tracks, userInputs)
            if jellyfin is not None:
                update_or_create_jellyfin_playlist(jellyfin, playlist, tracks, userInputs)
    else:
        logging.error("No spotify playlists found for given user")
