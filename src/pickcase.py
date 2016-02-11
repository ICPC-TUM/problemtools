#! /usr/bin/env python2
import os

class Picker:
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
	def pickcase(casefile,caseno):
		if not os.path.isfile(casefile):
			print 'Could not locate casefile file %s' % (casefile)
			return

		with open(casefile,'r') as f:
			empty = sum(not line.strip() for line in f)
			f.seek(0)
			cases=int(f.readline())

			if empty==0:
				lines = f.readlines()
				for line in lines:
					caseno -= 1
					if caseno == 0:
						return [line]
			elif empty==1:
				lines = f.readlines()
				foundempty=False
				for line in lines:
					if not foundempty:
						if not line.strip():
							foundempty=True
					else:
						caseno -= 1
						if caseno == 0:
							return [line]
			elif empty==cases-1:
				empty += 1
				caseno -= 1
				#sad replacement for switch with fallthrough
			if empty==cases:
				lines = f.readlines()
				ret=[]
				for line in lines:
					if not line.strip():
						caseno -= 1
						continue
					if caseno == 0:
						ret += [line]
					if caseno < 0:
						break
				return ret
			else:
				print "Could not deduce testcase layout"
				return []

if __name__ == '__main__':
	print Picker.pickcase("fail/fail1.in",Picker.firstfailingcase("fail/fail1.judgemessage","fail/fail1.ans"))
	# for i in range(1,6):
	# 	print firstfailingcase("fail/fail" + str(i) + ".judgemessage","fail/fail" + str(i) + ".ans")