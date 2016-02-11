#! /usr/bin/env python2
from verifyproblem import Problem,ProblemAspect,TestCaseGroup,Submissions,re_argument
from program import Program
import subprocess
import os
import re
import shutil
import logging
import sys
import random
from argparse import ArgumentParser, ArgumentTypeError
from pickcase import Picker

from timeit import default_timer as timer

class Fuzzer:
	RANDOMIZED_CASES=50
	MAX_FAILS = 5

	@staticmethod
	def _randomizeCase(original,randomized,cases,seed):
		with open(original, 'r') as f1:
			with open(randomized, 'w+') as f2:
				lines = f1.readlines()
				written = 0
				for i, line in enumerate(lines):
					if not line.startswith('#'):
						if written == 0:
							f2.write(str(cases) + "\n")
						elif written == 1:
							f2.write(seed + "\n")
						else:
							f2.write(line)
						written += 1

	@staticmethod
	def runRandomCase(args, logger):
		args.bail_on_error=False
		args.parts=["submissions"]
		ProblemAspect.silent=True

		with Problem(args.problemdir) as prob:
			datadir = os.path.join(prob.probdir, 'data')
			secretdir = os.path.join(datadir, 'secret')
			casefile = os.path.join(secretdir,args.case + '.seed')

			if not os.path.isfile(casefile):
				logger.error('Could not locate seed file %s' % (casefile))
				return

			if args.failpath is not None:
				if not os.path.isdir(args.failpath):
					logger.error('fail destination is not a directory')
					return
				if not os.access(args.failpath, os.W_OK):
					logger.error('could not write to fail destination')
					return

			program = Program(os.path.realpath(args.solution), prob.tmpdir)
			logger.info('Compiling program %s' % (program.name))

			if not program.compile():
				logger.error('Compile error for program %s' % (program.name))
				return


			#prepare the things we will need
			logger.info("preparing")
			subprocess.call(["make","generator"])
			subprocess.call(["make","anysolution"])

			FNULL = open(os.devnull, 'w')

			failed=0
			logger.info('finished %s runs of %s on %s (%s failed)' % (0,args.runs, args.case, 0))
			for i in range(args.runs):
				seed=str(random.getrandbits(63))
				randomized={}
				for ext in ['seed','in','ans']:
					randomized[ext] = os.path.join(secretdir,args.case + "_" + seed + "." + ext)

				logger.debug("randomizing %s"%(args.case))
				Fuzzer._randomizeCase(casefile,randomized["seed"],Fuzzer.RANDOMIZED_CASES,seed)
				#generate in and out file
				subprocess.call(["make",randomized["in"]],stdout=FNULL, stderr=subprocess.STDOUT)
				subprocess.call(["make",randomized["ans"]],stdout=FNULL, stderr=subprocess.STDOUT)
				#update testdata
				testdata = TestCaseGroup(prob, os.path.join(prob.probdir, 'data'))
				
				#run problemtools
				logger.debug("preparing and running problem tools")
				args.data_filter=re_argument(args.case +"_" + seed)
				(result1, result2) = testdata.run_submission(program,args)

				if str(result1)[:2] != 0:
					logger.debug("found problematic input, picking failing case")
					feedbackdir = os.path.join(prob.tmpdir,"lastfeedback")
					judgemessage = os.path.join(feedbackdir,"judgemessage.txt")
					case = Picker.pickcase(randomized["in"],Picker.firstfailingcase(judgemessage,randomized["ans"]))
					with open(randomized["in"],'w+') as f:
						f.write("1\n")
						for line in case:
							f.write(line)
					subprocess.call(["make",randomized["ans"]],stdout=FNULL, stderr=subprocess.STDOUT)
					
					logger.debug("running problem again on singular case")
					(result1, result2) = testdata.run_submission(program,args)

					if str(result1)[:2] != 0:
						failed += 1
						if args.failpath is not None:
							for ext in ['seed','in','ans']:
								dest = os.path.join(args.failpath,"fail" + str(failed) + "." + ext)
								shutil.copy(randomized[ext], dest)
							output = os.path.join(prob.tmpdir,"output")
							outputdest = os.path.join(args.failpath,"fail" + str(failed) + ".out")
							shutil.copy(output, outputdest)
							judgemessage = os.path.join(feedbackdir,"judgemessage.txt")
							judgemessagedest = os.path.join(args.failpath,"fail" + str(failed) + ".judgemessage")
							shutil.copy(judgemessage, judgemessagedest)
							diffposition = os.path.join(feedbackdir,"diffposition.txt")
							if os.path.isfile(diffposition):
								diffpositiondest = os.path.join(args.failpath,"fail" + str(failed) + ".diffposition")
								shutil.copy(diffposition, diffpositiondest)
						else:
							logger.info("found failing case:")
							with open(randomized['in']) as f:
								for line in f.readlines():
									logger.info(line)
					else :
						print "Solution has feedback errors between test cases"
						return
				
				logger.info('finished %s runs of %s on %s (%s failed)' % (i+1,args.runs, args.case, failed))
				
				for ext in ['seed','in','ans']:
					os.remove(randomized[ext])

				if failed >= Fuzzer.MAX_FAILS:
					logger.info('enough runs failed, ending run')
					return

	@staticmethod
	def argparser():
		parser = ArgumentParser(description="Run randomized cases")
		parser.add_argument("-t", "--fixed_timelim", help="use this fixed time limit (useful in combination with -d and/or -s when all AC submissions might not be run on all data)", type=int)
		parser.add_argument("-l", "--log-level", dest="loglevel", help="set log level (debug, info, warning, error, critical)", default="info")
		parser.add_argument("-r", "--runs", dest="runs", help="set the number of runs", default=10)
		parser.add_argument("-c", "--case", dest="case", help="set the base case which is then randomized", default="small1")
		parser.add_argument("-f", "--failpath", dest="failpath",help="set the path where the failing cases should be stored", default=None)
		parser.add_argument('problemdir')
		parser.add_argument('solution')
		return parser

	@staticmethod
	def default_args():
		return Fuzzer.argparser().parse_args([None,None])


if __name__ == '__main__':
	args = Fuzzer.default_args()
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

	Fuzzer.runRandomCase(args,logger)