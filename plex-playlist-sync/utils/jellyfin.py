import csv
import json
import logging
import pathlib
import subprocess
import sys
from difflib import SequenceMatcher
from typing import List

import plexapi

from .helperClasses import Playlist, Track, UserInputs

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def _write_csv(tracks: List[Track], name: str, path: str = "/data") -> None:
    """Write given tracks with given name as a csv.

    Args:
        tracks (List[Track]): List of Track objects
        name (str): Name of the file to write
        path (str): Root directory to write the file
    """
    # pathlib.Path(path).mkdir(parents=True, exist_ok=True)

    data_folder = pathlib.Path(path)
    data_folder.mkdir(parents=True, exist_ok=True)
    file = data_folder / f"{name}.csv"

    with open(file, "w", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(Track.__annotations__.keys())
        for track in tracks:
            writer.writerow(
                [track.title, track.artist, track.album, track.url]
            )


def _delete_csv(name: str, path: str = "/data") -> None:
    """Delete file associated with given name

    Args:
        name (str): Name of the file to delete
        path (str, optional): Root directory to delete the file from
    """
    data_folder = pathlib.Path(path)
    file = data_folder / f"{name}.csv"
    file.unlink()


def _get_available_jellyfin_tracks(jellyfin, tracks: List[Track], userinputs) -> List:

    jellyfin_tracks, missing_tracks = [], []
    for track in tracks:
        search = []
        try:
            if track.title != "":
                # logging.info("searching for ", track.title)
                search = jellyfin.search.get(track.title, None, None, None, "Audio", None, "Audio", None, None, None, None, None, None, False, True, False, False, True)
        except Exception:
            logging.info("failed to search %s on jellyfin", track.title)
        found = False
        if search:
            for s in search.search_hints:
                try:
                    #jellyfin search is not strict, continue to next index if track name does no match
                    track_similarity = SequenceMatcher(None, s.name.lower(), track.title.lower()).quick_ratio()
                    if track_similarity <= 0.9:
                        continue

                    if hasattr(s, 'album_artist') != None:
                        artist_similarity = SequenceMatcher(None, s.album_artist.lower(), track.artist.lower()).quick_ratio()
                        if artist_similarity >= 0.9:
                            jellyfin_tracks.append(s.id)
                            found = True
                            break

                    if s.album != None:
                        album_similarity = SequenceMatcher(None, s.album.lower(), track.album.lower()).quick_ratio()
                        if album_similarity >= 0.9:
                            jellyfin_tracks.append(s.id)
                            found = True
                            break

                except IndexError:
                    logging.info(
                        "Looks like jellyfin mismatched the search for %s,"
                        " retrying with next result"
                    )
        if not found:
            # download_song(userinputs, track)
            missing_tracks.append(track)

    return jellyfin_tracks, missing_tracks

def download_song(userinputs: UserInputs, track):
    command = ("ytmdl -q -o '/home/muhumbulom/PycharmProjects/plex-playlist-sync/download$Artist->Album->[Title]' --spotify-id '"
               + track.url + "' --album '" + track.album + "' --artist '" + track.album + "' '" + track.title+"'")

    # Execute the command
    subprocess.run(command, shell=True)
def _update_jellyfin_playlist(
    jellyfin,
    available_tracks: List,
    playlist: Playlist,
    append: bool = False,
) -> plexapi.playlist.Playlist:

    plex_playlist = jellyfin.playlists.create_playlist(playlist.name)
    if not append:
        plex_playlist.removeItems(plex_playlist.items())
    plex_playlist.addItems(available_tracks)
    return plex_playlist


def sync_list_with_jellyfin_playlist(client = None, title = None, inputList = None):
    if title == None or client == None or not inputList:
        return
    user_id = client.auth.config.data['auth.user_id']

    payload = {
        "Name": title,
        "Ids": [],
        "UserId": user_id,
        "MediaType": None
    }

    for item in inputList:
        payload['Ids'].append(item['jellyfin_id'])
    print(str(json.dumps(payload)))
    response = client.jellyfin._post(handler="Playlists", params=payload)
    if 'Id' in response:
        print("Hopefully ;) created playlist: ", response['Id'])
    else:
        print(response)

def _update_playlist(jellyfin, playlistId, tracks, user_id):
    batch_size = 100
    for i in range(0, len(tracks), batch_size):
        batch = tracks[i:i + batch_size]
        jellyfin.playlists.add_to_playlist(playlistId, ",".join(batch), user_id)

def update_or_create_jellyfin_playlist(
    jellyfin,
    playlist: Playlist,
    tracks: List[Track],
    userInputs: UserInputs,
) -> None:

    users = jellyfin.user.get_users()
    user_id = next((user.id for user in users if user.name == userInputs.jellyfin_user), None)
    if user_id is None:
        raise ValueError("User not found")

    available_tracks, missing_tracks = _get_available_jellyfin_tracks(jellyfin, tracks, userInputs)
    if available_tracks:
        search = jellyfin.search.get(playlist.name, None, None, user_id, "Playlist", None, "Audio", None, None, None, None, None,
                                     None, False, True, False, False, True)
        if search and len(search.search_hints) > 0:
            for s in search.search_hints:
                # jellyfin search is not strict, continue to next index if playlist name does no match
                track_similarity = SequenceMatcher(None, s.name.lower(), playlist.name.lower()).quick_ratio()
                if track_similarity >= 0.9:
                    _update_playlist(jellyfin, s.id, available_tracks, user_id)
                    logging.info("Updated playlist %s with summary and poster", playlist.name)
                else:
                    continue
        else:
            playlist_id = jellyfin.playlists.create_playlist(playlist.name, "", user_id, "Audio")
            logging.info("Created playlist %s", playlist.name)
            _update_playlist(jellyfin, playlist_id.id, available_tracks, user_id)
            logging.info("Updated playlist %s with summary and poster", playlist.name)
    else:
        logging.info(
            "No songs for playlist %s were found on jellyfin, skipping the"
            " playlist creation",
            playlist.name,
        )

    if missing_tracks and userInputs.write_missing_as_csv:
        try:
            _write_csv(missing_tracks, playlist.name)
            logging.info("Missing tracks written to %s.csv", playlist.name)
        except:
            logging.info(
                "Failed to write missing tracks for %s, likely permission"
                " issue",
                playlist.name,
            )
    if (not missing_tracks) and userInputs.write_missing_as_csv:
        try:
            # Delete playlist created in prev run if no tracks are missing now
            _delete_csv(playlist.name)
            logging.info("Deleted old %s.csv", playlist.name)
        except:
            logging.info(
                "Failed to delete %s.csv, likely permission issue",
                playlist.name,
            )
