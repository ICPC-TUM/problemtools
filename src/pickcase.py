#! /usr/bin/env python2
import os
from argparse import ArgumentParser, ArgumentTypeError

class LayoutError(Exception):
    pass

class Picker:

	def __init__(self,layoutfile):
		if not os.path.isfile(layoutfile):
			print 'Could not locate layout file %s' % (layoutfile)
			return

		with open(layoutfile,'r') as f:
			empty = sum(not line.strip() for line in f)
			f.seek(0)
			cases=int(f.readline())
			if cases < 3:
				raise LayoutError("Given test case does not have at least 3 cases")
				
			if not empty in [0,1,cases-1,cases]:
				raise LayoutError("could not deduce testcase layout")
			self.preamble = False
			self.singleline = False
			if empty == 1 or empty == cases:
				self.preamble=True
			if empty<2:
				self.singleline=True

	def splitcase(self,casefile,first):
		if not os.path.isfile(casefile):
			print 'Could not locate casefile file %s' % (casefile)
			return

		with open(casefile,'r') as f:
			cases=int(f.readline())
			half = cases/2

			ret=[]

			if first:
				ret = [str(half)+"\n"]
			else:
				ret = [str(cases-half)+"\n"]

			if self.preamble:
				#read and save preamble
				ret = ret + self._readToEmpty(f) + ["\n"]

			for i in range(cases):
				if (i<half)==first:
					ret = ret + self._readCase(f)
					if not self.singleline:
						ret += ["\n"]
				else:
					self._readCase(f)

			if not self.singleline and len(ret)>1:
				#remove last empty line
				ret.pop()
			return ret

	@staticmethod
	def firstfailingcase(judgemessage,sol):
		if not os.path.isfile(judgemessage):
			print 'Could not locate judgemessage file %s' % (judgemessage)
			return
		if not os.path.isfile(sol):
			print 'Could not locate sol file %s' % (sol)
			return

		with open(judgemessage, 'r') as f1:
			answer=f1.readline()
			tokens=answer.split()
			if tokens[0] == "Testcase":
				case=tokens[1]
				#strip colon
				case=case[:-1]
				return int(case)
			elif tokens[0] == "Wrong":
				testline=int(tokens[10])
				with open(sol,'r') as f2:
					lines = f2.readlines()
					case=0
					for i, line in enumerate(lines):
						if line.startswith('Case #'):
							case += 1
						if i+1 == testline:
							return case
		return -1

	def _readToEmpty(self,f):
		res=[]
		line = f.readline()
		while line.strip():
			res=res+[line]
			line=f.readline()
		return res

	def _readCase(self,f):
		if self.singleline:
			return [f.readline()]
		else:
			return self._readToEmpty(f)

	def pickcase(self,casefile,caseno):
		if not os.path.isfile(casefile):
			print 'Could not locate casefile file %s' % (casefile)
			return

		with open(casefile,'r') as f:
			cases=int(f.readline())

			if caseno < 1 or caseno > cases:
				print "invalid case number: %d out of %d" % (caseno, cases)
				return []

			ret = ["1\n"]

			if self.preamble:
				#read and save preamble
				ret = ret + self._readToEmpty(f) + ["\n"]

			for i in range(caseno-1):
				self._readCase(f)

			ret = ret + self._readCase(f)

			return ret

	@staticmethod
	def argparser():
		parser = ArgumentParser(description="Run randomized cases")
		parser.add_argument('casefile')
		parser.add_argument('layoutfile')
		parser.add_argument("-c", "--case", dest="case", help="set the case to be picked", default=1)
		parser.add_argument("-s", "--split", dest="split", help="whether to split", default=None)
		return parser

	@staticmethod
	def default_args():
		return Fuzzer.argparser().parse_args([None,None])


if __name__ == '__main__':
	args = Picker.argparser().parse_args()
	p = Picker(args.layoutfile)
	if args.split is not None:
		if args.split == "first":
			print p.splitcase(args.casefile,True)
		else:
			print p.splitcase(args.casefile,False)
	else:
		print p.pickcase(args.casefile,int(args.case))