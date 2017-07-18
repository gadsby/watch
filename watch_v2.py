#!/usr/bin/env python3

import os
import sys
import json
import random
import argparse
import subprocess
import pandas as pd
import Levenshtein

def get_arg_parser():
	parser = argparse.ArgumentParser(description='Watch movies and tv.')
	parser.add_argument('title', nargs='*', default='', help='Title of Movie or TV Show.')
	group = parser.add_mutually_exclusive_group()
	group.add_argument('--list', action='store_true', help='List all available movies.')
	group.add_argument('--random', action='store_true', help='Request a random movie.')
	return parser.parse_args()

def get_input():
	if len(sys.argv) > 1:
		args = get_arg_parser()
		input_string = ' '.join(args.title)
		return input_string, args.list, args.random
	else:
		print('No arguments passed')
		exit()

def load_settings(config_path):
	with open(config_path, 'r') as config:
		settings = json.loads(config.read())
	min_display = settings['min_display']
	data_path = settings['data_path']
	weights = [settings['weights'][name] for name in ['longest_common_substring', 'levenshtein', 'offset']]
	inventory_path = settings['inventory_path']
	return min_display, data_path, weights, inventory_path

def verify_path(data_path):
	if not os.path.exists(data_path):
		print('Data path does not exist')
		exit()
	else:
		movie_path = data_path + 'Movies/'
		tv_path = data_path + 'TV/'
		return movie_path, tv_path

def gen_dataframe_film(movie_path):
	year_list = []
	for file in os.listdir(movie_path):
		if not file.startswith('.') and file.isnumeric():
			year_list.append(file)
	year_list.sort(reverse=True)
	file_list, full_path = [], []
	for year in year_list:
		raw_films = []
		for file in os.listdir(movie_path+year):
			if not file.startswith('.'):
				raw_films.append(file)
		raw_films.sort()
		file_list += raw_films
		full_path += ['{}{}/{}'.format(movie_path,year,file) for file in raw_films]
	film_df = pd.DataFrame([file_list, full_path, [True]*len(file_list)]).T
	film_df.columns = ['Title', 'full_path', 'is_movie']
	film_df['Title'] = film_df[['Title']].applymap(lambda file: file.split('.')[0])
	return film_df

def generate_random_options(dataframe_film):
	rand_title = dataframe_film.Title[random.randint(0,len(dataframe_film)-1)]
	selection = input('{}? Y/[N]'.format(rand_title))
	if selection.lower().startswith('y'):
		launch_random_video(dataframe_film, rand_title)
	elif selection.lower().startswith('n') or not len(selection):
		pass
	else:
		print('Not a valid option')
		exit()

def launch_random_video(dataframe_film, rand_title):
	path_for_random = dataframe_film[dataframe_film.Title == rand_title].full_path.values[0]
	print('Opening...')
	subprocess.call(['open', '-a', '/Applications/VLC.app', path_for_random])
	exit()

def launch_video(dataframe, selection):
	video_selection = dataframe[dataframe.index == selection].full_path.values[0]
	print('Opening...')
	subprocess.call(['open', '-a', '/Applications/VLC.app', video_selection])
	exit()

def gen_dataframe_tv(tv_path):
	tv_list = []
	for file in os.listdir(tv_path):
		if not file.startswith('.') and os.path.isdir(tv_path+file):
			tv_list.append(file)
	tv_list.sort()
	tv_df = pd.DataFrame([tv_list, ['N/A']*len(tv_list), [False]*len(tv_list)]).T
	tv_df.columns = ['Title', 'full_path', 'is_movie']
	return tv_df

def longest_common_substring_length(s1, s2):
	m = [[0] * (1 + len(s2)) for i in range(1 + len(s1))]
	longest = 0
	for x in range(1, 1 + len(s1)):
		for y in range(1, 1 + len(s2)):
			if s1[x - 1] == s2[y - 1]:
				m[x][y] = m[x - 1][y - 1] + 1
				longest = max(m[x][y], longest)
			else:
				m[x][y] = 0
	return longest

def similarity_metric(name, input_string, weights):
	name, input_string = name.lower(), input_string.lower()
	return weights[0]*longest_common_substring_length(name,input_string) \
		 + weights[1]*Levenshtein.ratio(name,input_string)

def reindex_on_similarity(input_string, master_df, weights):
	master_df['Similarity'] = master_df[['Title']].applymap(lambda name: similarity_metric(name, input_string, weights))
	master_df = master_df.sort_values(by='Similarity', ascending=False)
	master_df = master_df.reset_index()
	master_df.index = range(1, len(master_df) + 1)
	return master_df

def display_options(master_df, min_display, weights):
	candidates = master_df[master_df.Similarity >= sum(weights)]
	num_display = max(len(candidates), min_display)
	print(master_df[['Title']].head(num_display).to_csv(sep='\t'), end='')
	print('{}\t<New Movie Torrent>'.format(num_display+1))
	return num_display

def parse_selection(max_selection, default, default_str):
	selection = input('Select an option, or press enter for {}: '.format(default_str))
	if not len(selection): return default
	if selection.isnumeric() and int(selection) in range(1,max_selection+1):
		return int(selection)
	else:
		print('Not a valid option')
		exit()

def launch_torrent_request(input_string):
	pirate_URL = 'https://thepiratebay.org/search/{}/0/99/0'.format(input_string.replace(' ','%20'))
	subprocess.call(['open', '-a', '/Applications/Google\ Chrome.app/', pirate_URL])
	exit()

def get_seasons_for_title(tv_title):
	seasons = []
	for file in os.listdir(tv_path+tv_title):
		if not file.startswith('.'):
			seasons.append(file)
	seasons.sort()
	return seasons

def select_tv_season(seasons):
	if len(seasons) > 1:
		season_df = pd.DataFrame(seasons, columns=['Season'])
		season_df.index = range(1, len(season_df) + 1)
		print('')
		print(season_df[['Season']].to_csv(sep='\t'), end='')
		selection = parse_selection(max_selection=len(season_df), default=len(season_df), default_str='latest season')
		return season_df[season_df.index == selection].Season.values[0]
	else:
		return seasons[0]

def get_episode_list(tv_path, tv_title, season_selection):
	episode_list = []
	for file in os.listdir('{}{}/{}'.format(tv_path, tv_title, season_selection)):
		if not file.startswith('.'):
			episode_list.append(file)
	try:
		sort_key = lambda file: (len(file.split(' ')[0]), float(file.split(' ')[0]))
		episode_list.sort(key=sort_key)
	except ValueError:
		episode_list.sort()
	return episode_list

def gen_episode_dataframe(episode_list, tv_path, tv_title, season_selection):
	episode_paths = []
	for episode in episode_list:
		episode_path = '{}{}/{}/{}'.format(tv_path, tv_title, season_selection, episode)
		episode_paths.append(episode_path)
	episode_df = pd.DataFrame([episode_list, episode_paths]).T
	episode_df.columns = ['Episode', 'full_path']
	episode_df['Episode'] = episode_df[['Episode']].applymap(lambda filename: '.'.join(filename.split('.')[:-1]))
	episode_df.index = range(1, len(episode_df) + 1)
	return episode_df

def display_episode_df(episode_df):
	print('')
	print(episode_df[['Episode']].to_csv(sep='\t'), end='')


if __name__ == "__main__":

	try:

		input_string, list_all_films, get_random_film = get_input()
		min_display, data_path, weights, inventory_path = \
                        load_settings('/Users/olivergadsby/execFiles/watch_v2/config_watch.json')

		if list_all_films:
			subprocess.call(['less', inventory_path])
			exit()

		movie_path, tv_path = verify_path(data_path)

		film_df = gen_dataframe_film(movie_path)
		tv_df = gen_dataframe_tv(tv_path)
		master_df = pd.concat([film_df, tv_df])
		master_df = reindex_on_similarity(input_string, master_df, weights)

		if get_random_film:
			while True:
				generate_random_options(film_df)

		num_display = display_options(master_df, min_display, weights)
		selection = parse_selection(max_selection=num_display+1, default=1, default_str='closest match')

		if selection == num_display+1:
			launch_torrent_request(input_string)

		else:
			if master_df[master_df.index == selection].is_movie.values[0]:
				launch_video(master_df, selection)
			else:
				tv_title = master_df[master_df.index == selection].Title.values[0]
				seasons = get_seasons_for_title(tv_title)
				season_selection = select_tv_season(seasons)
				episode_list = get_episode_list(tv_path, tv_title, season_selection)
				episode_df = gen_episode_dataframe(episode_list, tv_path, tv_title, season_selection)
				display_episode_df(episode_df)
				selection = parse_selection(max_selection=len(episode_df), default=len(episode_df), default_str='latest episode')
				launch_video(episode_df, selection)

	except:
		pass



