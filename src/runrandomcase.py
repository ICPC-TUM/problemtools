#! /usr/bin/env python2
# -*- coding: utf-8 -*-
import glob
import string
import hashlib
import collections
import os
import signal
import re
import shutil
import logging
import yaml
import tempfile
import sys
import copy
import random
from argparse import ArgumentParser, ArgumentTypeError
from program import Executable, Program, ValidationScript, ProgramError, ProgramWarning, locate_program
from verifyproblem import *
import random

#NEW METHODS FOR PROBLEM
def newenter(self):
	self.tmpdir = tempfile.mkdtemp(prefix='verify-%s-'%self.shortname)
	if not os.path.isdir(self.probdir):
		self.error("Problem directory '%s' not found" % self.probdir)
		self.shortname = None
		return self

	self.statement = ProblemStatement(self)
	self.config = ProblemConfig(self)
	self.output_validators = OutputValidators(self)
	self.testdata = TestCaseGroup(self, os.path.join(self.probdir, 'data'))
	self.submissions=None
	self.is_interactive = False
	return self

def runRandomCase(self,args,logger,failpath):
	if self.shortname is None:
		return [1, 0]
	if args is None:
		args = default_args()

	try:
		if not re.match('^[a-z0-9]+$', self.shortname):
			logger.error("Invalid shortname '%s' (must be [a-z0-9]+)" % self.shortname)

		#here is the actual testing

		#first locate and compile sample sol and generator
		srcdir = os.path.join(self.probdir, 'submissions')
		samplesol = get_programs(os.path.join(srcdir, 'accepted'),
			self.tmpdir, pattern=Submissions._SUB_REGEXP, error_handler=self)[0]

		generator =	get_programs(os.path.join(self.probdir,'generators'),
			self.tmpdir,error_handler=self)[0]

		logger.info('Compiling sample solution %s' % (samplesol.name))
		if not samplesol.compile():
			logger.error('Compile error for sample solution %s' % (samplesol.name))
			return

		logger.info('Compiling generator %s' % (generator.name))
		if not generator.compile():
			logger.error('Compile error for generator %s' % (generator.name))
			return

		#compile the program
		program = Program(os.path.realpath(args.solution), self.tmpdir)
		logger.info('Compiling program %s' % (program.name))

		if not program.compile():
			logger.error('Compile error for program %s' % (program.name))
			return

		#check fail destination
		if not os.path.isdir(failpath):
			logger.error('fail destination is not a directory')
			return

		if not os.access(failpath, os.W_OK):
			logger.error('could not write to fail destination')
			return

		#locate and copy test case

		datadir = os.path.join(self.probdir, 'data')
		secretdir = os.path.join(datadir, 'secret')
		casefile = os.path.join(secretdir,args.case + '.seed')

		if not os.path.isfile(casefile):
			self.error('Could not locate seed file %s' % (casefile))
			return

		tmpdatadir = os.path.join(self.tmpdir,'data')
		
		os.mkdir(tmpdatadir)

		logger.info('finished 0 runs of %s on %s (0 failed)' % (args.runs, args.case))
		
		failed=0
		randomized = os.path.join(tmpdatadir,args.case)
		
		for i in range(args.runs):
			#copy and randomize case
			logger.debug("randomizing seed for %s" % args.case)		
			Fuzzer._randomizeCase(casefile,randomized + ".seed")

			#generate infile
			logger.debug("generating randomized test case in/ans")
			generator.run(randomized + '.seed', randomized + '.in',timelim=100, logger=None, errfile='errors')

			samplesol.run(randomized + '.in', randomized + '.ans',timelim=100, logger=None, errfile='errors')

			logger.debug("run program %s" % program.name)
			testcasegroup = TestCaseGroup(self,tmpdatadir)

			(result1, result2) = testcasegroup.run_submission(program,args)
			logger.debug('verdict: %s' % (result1))

			if str(result1)[:2] != "AC":
				failed += 1
				for ext in ['.seed','.in','.ans']:
					dest = os.path.join(failpath,"fail" + str(failed) + ext)
					shutil.copy(randomized + ext, dest)
				output = os.path.join(self.tmpdir,"output")
				outputdest = os.path.join(failpath,"fail" + str(failed) + ".out")
				shutil.copy(output, outputdest)
				feedbackdir = os.path.join(self.tmpdir,"lastfeedback")
				judgemessage = os.path.join(feedbackdir,"judgemessage.txt")
				judgemessagedest = os.path.join(failpath,"fail" + str(failed) + ".judgemessage")
				diffposition = os.path.join(feedbackdir,"diffposition.txt")
				diffpositiondest = os.path.join(failpath,"fail" + str(failed) + ".diffposition")
				shutil.copy(judgemessage, judgemessagedest)
				shutil.copy(diffposition, diffpositiondest)

			logger.info('finished %s runs of %s on %s (%s failed)' % (i+1,args.runs, args.case, failed))

			if failed >= 5:
				logger.info('five runs failed, ending run')
				return

	except VerifyError:
		pass

#silence verifyproblem
def newinit(self):
	silent=True

#the fuzzer class
class Fuzzer:
	def __init__(self):
		Problem.__enter__ = newenter
		Problem.runRandomCase = runRandomCase
		#ProblemAspect.__init__=newinit
		ProblemAspect.silent=True

	@staticmethod
	def _randomizeCase(original,randomized):
		with open(original, 'r') as f1:
			with open(randomized, 'w+') as f2:
				lines = f1.readlines()
				written = 0
				for i, line in enumerate(lines):
					if not line.startswith('#'):
						if written == 0:
							f2.write("1\n")
						elif written == 1:
							f2.write(str(random.getrandbits(63)) + "\n")
						else:
							f2.write(line)
						written += 1

	def checkFuzzy(self,args,logger,failpath):
		with Problem(args.problemdir) as prob:
			prob.runRandomCase(args,logger,failpath)

	@staticmethod
	def argparser():
		parser = ArgumentParser(description="Validate a problem package in the Kattis problem format.")
		parser.add_argument("-s", "--submission_filter", metavar='SUBMISSIONS', help="run only submissions whose name contains this regex.  The name includes category (accepted, wrong_answer, etc), e.g. 'accepted/hello.java' (for a single file submission) or 'wrong_answer/hello' (for a directory submission)", type=re_argument, default=re.compile('.*'))
		parser.add_argument("-t", "--fixed_timelim", help="use this fixed time limit (useful in combination with -d and/or -s when all AC submissions might not be run on all data)", type=int)
		parser.add_argument("-l", "--log-level", dest="loglevel", help="set log level (debug, info, warning, error, critical)", default="info")
		parser.add_argument("-r", "--runs", dest="runs", help="", default=10)
		parser.add_argument("-c", "--case", dest="case", help="", default="small1")
		parser.add_argument('problemdir')
		parser.add_argument('solution')
		return parser

	@staticmethod
	def default_args():
		return Fuzzer.argparser().parse_args([None])


if __name__ == '__main__':
	args = Fuzzer.argparser().parse_args()
	#args.data_filter=re.compile(".*")
	args.data_filter=re.compile("data/" + args.case + "$")
	fmt = "%(levelname)s %(message)s"
	#silence verifyproblem
	logging.basicConfig(stream=sys.stdout,
						format=fmt,
						level=eval("logging.CRITICAL"))

	logger=logging.getLogger("fuzzylogger")
	logger.setLevel(eval("logging." + args.loglevel.upper()))

	print 'Loading problem %s' % os.path.basename(os.path.realpath(args.problemdir))
	f = Fuzzer()
	f.checkFuzzy(args, logger, "fail")
