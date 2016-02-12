#! /usr/bin/env python2
import os

class Picker:
	@staticmethod
	def splitcase(casefile,first):
		if not os.path.isfile(casefile):
			print 'Could not locate casefile file %s' % (casefile)
			return

		with open(casefile,'r') as f:
			empty = sum(not line.strip() for line in f)
			f.seek(0)
			cases=int(f.readline())
			half = cases/2

			rest=[]

			if first:
				ret = [str(half)+"\n"]
			else:
				ret = [str(cases-half)+"\n"]

			if not empty in [0,1,cases-1,cases]:
				print "could not deduce testcase layout"
				return []

			if empty==1 or empty==cases:
				#read and save preamble
				ret = ret + Picker.readToEmpty(f) + ["\n"]
				empty -= 1

			for i in range(cases):
				if (i<half)==first:
					ret = ret + Picker.readCase(f,empty)
					if empty:
						ret += ["\n"]
				else:
					Picker.readCase(f,empty)

			if empty:
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

	@staticmethod
	def readToEmpty(f):
		res=[]
		line = f.readline()
		while line.strip():
			res=res+[line]
			line=f.readline()
		return res

	@staticmethod
	def readCase(f,empty):
		if (empty == 0):
			return [f.readline()]
		else:
			return Picker.readToEmpty(f)

	@staticmethod
	def pickcase(casefile,caseno):
		if not os.path.isfile(casefile):
			print 'Could not locate casefile file %s' % (casefile)
			return

		with open(casefile,'r') as f:
			empty = sum(not line.strip() for line in f)
			f.seek(0)
			cases=int(f.readline())

			if caseno < 1 or caseno > cases:
				print "invalid case number"
				return []

			if not empty in [0,1,cases-1,cases]:
				print "could not deduce testcase layout"
				return []

			ret = ["1\n"]

			if empty==1 or empty==cases:
				#read and save preamble
				ret = ret + Picker.readToEmpty(f) + ["\n"]
				empty -= 1

			for i in range(caseno-1):
				Picker.readCase(f,empty)

			ret = ret + Picker.readCase(f,empty)

			return ret

if __name__ == '__main__':
	print Picker.splitcase("fail/fail1.in",True)
	print Picker.splitcase("fail/fail1.in",False)
	# for i in range(1,6):
	# 	print firstfailingcase("fail/fail" + str(i) + ".judgemessage","fail/fail" + str(i) + ".ans")