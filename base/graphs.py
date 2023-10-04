import numpy as np

#gives directional chip ids for chips on a tile

class NumberedArrangement:

	def __init__(self, nrows=10, ncols=10, start_index=11):
		self.nrows = nrows
		self.ncols = ncols
		self.start_index = start_index
		self.excluded_links = set()
		self.excluded_chips = set()
		self.good_connections = set()

		self.m1 =[self.right, self.left, self.down, self.up]
		self.m2 =[self.right, self.left, self.up, self.down]
		self.m3 =[self.right, self.up, self.down, self.left]
		self.m4 =[self.right, self.up, self.left, self.down]
		self.m5 =[self.right, self.down, self.up, self.left]
		self.m6 =[self.right, self.down, self.left, self.up]
		self.m7 =[self.left, self.right, self.up, self.down]
		self.m8 =[self.left, self.right, self.down, self.up]
		self.m9 =[self.left, self.down, self.up, self.right]
		self.m10=[self.left, self.down, self.right, self.up]
		self.m11=[self.left, self.up, self.down, self.right]
		self.m12=[self.left, self.up, self.right, self.down]
		self.m13=[self.down, self.right, self.left, self.up]
		self.m14=[self.down, self.right, self.up, self.left]
		self.m15=[self.down, self.left, self.up, self.right]
		self.m16=[self.down, self.left, self.right, self.up]
		self.m17=[self.down, self.up, self.left, self.right]
		self.m18=[self.down, self.up, self.right, self.left]
		self.m19=[self.up, self.right, self.left, self.down]
		self.m20=[self.up, self.right, self.down, self.left]
		self.m21=[self.up, self.left, self.down, self.right]
		self.m22=[self.up, self.left, self.right, self.down]
		self.m23=[self.up, self.down, self.left, self.right]
		self.m24=[self.up, self.down, self.right, self.left]

		self.all_dir_maps = [self.m1, self.m2, self.m3, self.m4, self.m5, self.m6, self.m7, self.m8, self.m9, self.m10, self.m11, self.m12, self.m13, self.m14, self.m15, self.m16, self.m17, self.m18, self.m19, self.m20, self.m21, self.m22, self.m23, self.m24]
		self.n_maps = len(self.all_dir_maps)
		#use grid points to create path
		self.grid = [ [None for row in range(self.nrows)] for col in range(self.ncols) ]
		return

	def get_mover(self, ind1, ind2):
		for mover in self.base_dir_map:
			if mover(ind1) == ind2:
				return mover
		return self.no_move

	def get_adjacent_mover(self, ind1, ind2):
		for im, mover in enumerate(self.base_dir_map):
			if mover(ind1) == ind2:
				return self.adjecent_dir_map[im]
		return self.no_move

	def get_opposite_mover(self, ind1, ind2):
		for im, mover in enumerate(self.base_dir_map):
			if mover(ind1) == ind2:
				return self.opposite_dir_map[im]
		return self.no_move

	def all_chips(self):
		return [i for i in range(self.start_index, self.start_index + self.ncols*self.nrows) if not (i in self.excluded_chips)]

	#number of steps between two chips
	def distance(self, ind1, ind2):
		if ind1 < self.start_index or ind2 < self.start_index:
			return 9999
		row1, col1 = self.row_col(ind1)
		row2, col2 = self.row_col(ind2)
		return np.abs(row1-row2) + np.abs(col1-col2)

	def add_good_connection(self, link):
		self.good_connections.add(link)
		self.good_connections.add((link[1], link[0]))

	def add_excluded_link(self, link):
		self.excluded_links.add(link)
		self.excluded_links.add( (link[1], link[0]) )

	def add_onesided_excluded_link(self, link):
		self.excluded_links.add(link)

	def add_excluded_chip(self, chip_id):
		self.excluded_chips.add(chip_id)

	def index(self, row, col):
		return self.start_index + self.ncols*row + col

	def row(self, chip):
		r, c = self.row_col(chip)
		return r
	def col(self, chip):
		r, c = self.row_col(chip)
		return c

	def clear(self):
		self.excluded_chips = set()
		self.excluded_links = set()
		self.good_connections = set()

	def row_col(self, index):
		row_index = (index - self.start_index) // self.ncols
		col_index = (index - self.start_index) - self.ncols * row_index
		return row_index, col_index

	def left(self, _index):
		row, col = self.row_col(_index)
		return self.index(row, col-1) if col-1 >= 0 else -1

	def right(self, _index):
		row, col = self.row_col(_index)
		return self.index(row, col+1) if col+1 < self.ncols else -1

	def down(self, _index):
		row, col = self.row_col(_index)
		return self.index(row+1, col) if row+1 < self.nrows else -1

	def up(self, _index):
		row, col = self.row_col(_index)
		return self.index(row-1, col) if row-1  >= 0 else -1

	def no_move(self, _index):
		print('tried to move from', _index, ', no move')
		return _index

	def get_map(self, ind1, ind2):
		if self.up(ind1) == ind2:
			return [ind2,None,None,None]
		elif self.left(ind1) == ind2:
			return [None, ind2, None, None]
		elif self.down(ind1) == ind2:
			return [None,None,ind2,None]
		elif self.right(ind1) == ind2:
			return [None, None, None, ind2]
		else:
			return [None, None, None, None]

	def get_map_index(self, ind1, ind2):
		if self.up(ind1) == ind2:
			return 0
		elif self.left(ind1) == ind2:
			return 1
		elif self.down(ind1) == ind2:
			return 2
		elif self.right(ind1) == ind2:
			return 3
		else:
			return -1

	def get_uart_enable_list(self, ind1, ind2=-1):
		if ind2 == -1:
			#only for root chips
			return [1,0,0,0]
		if self.left(ind1) == ind2:
			return [1,0,0,0]
		if self.down(ind1) == ind2:
			return [0,1,0,0]
		if self.right(ind1) == ind2:
			return [0,0,1,0]
		if self.up(ind1) == ind2:
			return [0,0,0,1]

	def connect_chips(self, start, end, extra_excluded_chips=[]):
		#gives a path connecting start to end
		#excludes forbidden chips and uart connections
		base_direction_map = [self.left, self.right, self.down, self.up]
		path = [start]
		while not (path[-1] == end):
			curr = path[-1]
			possible_steps = []
			for direction in base_direction_map:
				pstep = direction(curr)
				if (curr, pstep) in self.excluded_links or (pstep, curr) in self.excluded_links:
					continue
				if pstep in self.excluded_chips:
					continue
				if pstep in extra_excluded_chips:
					continue
				if pstep in path:
					continue
				if pstep < 0:
					continue
				possible_steps.append(pstep)

			if len(possible_steps) == 0:
				return []

			distance_map = [self.distance(end, step) for step in possible_steps]
			best_steps_index = np.argmin(distance_map)
			#print(best_steps_index)
			path.append(possible_steps[best_steps_index])

		return path

	def get_path_sub(self, existing_path=None, ind=0):
		if existing_path is None:
			existing_path = [[self.start_index]]

		#prefers right, down, left, up

		direction_map = self.all_dir_maps[ind]
		still_stepping = [False for path in existing_path]

		new_paths = existing_path.copy()

		for ipath, path in enumerate(existing_path):

			starting_point = path[-1]
			for direction in direction_map:
				next_id = direction(starting_point)

				if next_id < 0:
					continue

				if any( [next_id in path for path in existing_path] ):
					continue

				if next_id in self.excluded_chips:
					continue

				if (starting_point, next_id) in self.excluded_links:
					exclude = []
					for p in new_paths:
						exclude += p
					addon = self.connect_chips(starting_point, next_id, exclude)
					if len(addon) == 0:
						continue

					new_paths[ipath] += addon[1:]
					still_stepping[ipath] = True
					break

				if next_id in self.excluded_chips:
					continue

				new_paths[ipath] += [next_id]
				still_stepping[ipath] = True
				break

		if any(still_stepping):
			return self.get_path_sub(new_paths, ind)

		return new_paths

	def get_path(self, existing_path=None):
		def length(path_list):
			l = 0
			for p in path_list:
				l += len(p)
			return l

		new_paths = []
		for path in existing_path:
			new_paths.append(path.copy())

		all_lengths = []
		for i in range(len(self.all_dir_maps)):
			new_new_paths = []
			for path in new_paths:
				new_new_paths.append(path.copy())
			paths = self.get_path_sub(new_new_paths, i)
			all_lengths.append(length(paths))
		#print(all_lengths)
		i = np.argmax(all_lengths)
		return self.get_path_sub(existing_path.copy(), i)

























