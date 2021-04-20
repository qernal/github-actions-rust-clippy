import json
import subprocess
import os
import glob
import base64
import random
import sys
from concurrent.futures import ThreadPoolExecutor, wait

class Clippy:
    config = dict()
    args = [
        "cargo",
        "clippy",
        "--message-format=json"
    ]
    compiler_output = list()
    github_output = list()

    # execute the clippy command
    def exec(self, dir):
        command = self.build_command()
        print("-- COMMAND: ", command)

        try:
            process = subprocess.Popen(command, stdout = subprocess.PIPE, shell=True, cwd=dir)
            output = process.stdout.readlines()
            process.wait()

            if process.returncode != 0:
                print('Non-zero exit code; ', process.returncode)
                exit(1)

            return output
        except subprocess.CalledProcessError as e:
            print("Error in calling cargo; ", e.output)
            return None
        except:
            print("Unexpected error:", sys.exc_info()[0])
            return None

    # build command with args
    def build_command(self):
        gen_args = []

        if 'ssh' in self.config and self.config['ssh']:
            gen_args.append('eval $(ssh-agent -s)')
            gen_args.append('&&')
            gen_args.append('ssh-add /root/.ssh/id_rsa')
            gen_args.append('&&')

        # CARGO_TARGET_DIR=/tmp/(rand) << prepend this to the command, randomise the dir for each cargo run
        rand_path = ''.join(str(random.randrange(0, 9)) for i in range(10))

        # make new cargo directory
        gen_args.append("mkdir -p /tmp/" + rand_path)
        gen_args.append('&&')

        # copy cargo
        gen_args.append("cp -r ~/.cargo/ /tmp/" + rand_path + "/")
        gen_args.append('&&')

        # vars for cargo to work in another location
        gen_args.append("PATH=$PATH:/tmp/" + rand_path + "/.cargo/bin/")
        gen_args.append("CARGO_HOME=/tmp/" + rand_path)

        return ' '.join(gen_args + self.args)

    # main handler
    def run(self, dir):
        localPaths = []

        if 'path_glob' in self.config:
            for path in glob.glob("/".join([dir, self.config['path_glob']])):
                if os.path.exists("".join([path, "Cargo.toml"])):
                    print('Globbed path, found Cargo at: ', path)
                    localPaths.append(path)

            print("Creating executor, theads of;", self.config['threads'])
            executor = ThreadPoolExecutor(max_workers=self.config['threads'])
            futures = []
            for path in localPaths:
                print("-- THREAD: Creating submission for; ", path)
                futures.append(executor.submit(self.compile, path))

            # wait for all clippy's to complete
            wait(futures)
        else:
            self.compile(dir)

        for message in self.github_output:
            print(message.replace('\n', '%0A').replace('\r', '%0D'))

    # compile the command and output together
    def compile(self, dir):
        output = self.exec(dir)
        self.process_output(output, dir)
        self.generate_github_output()

    # process clippy output
    def process_output(self, output, dir):
        for line in output:
            try:
                line = line.strip()
                json_line = json.loads(line)

                if "reason" in json_line:
                    if json_line['reason'] == "compiler-message":
                        # we'll accept this and add it to our compiler output
                        self.compiler_output.append({"json": json_line, "path": dir})
            # not a json line so, we'll skip
            except AttributeError:
                print('Skipping line in output; ', line)
            except ValueError:
                print('Skipping line in output; ', line)

    # convert compiler output to github output
    def generate_github_output(self):
        for json_line in self.compiler_output:
            gh_output = self.line_compiler_to_gh(json_line['json'], json_line['path'])

            if gh_output != None:
                self.github_output.append(gh_output)

    # convert each compiler line to a valid github warning or error
    def line_compiler_to_gh(self, json_line, dir):
        level = json_line['message']['level']
        path = self.find_compiler_path(json_line)
        message = json_line['message']['rendered']
        span = self.find_compiler_span(json_line, path)

        if path == None or span == None:
            return None

        if 'path_glob' in self.config:
            path = dir.replace(self.config['base_dir'] + "/", "") + path

        if level == "warning":
            return f"::warning file={path},line={span['line_start']},col={span['column_start']}::{message}"

        if level == "error":
            return f"::error file={path},line={span['line_start']},col={span['column_start']}::{message}"

        print("Line was missing compiler information")
        return None

    # find the span with valid file names and error codes
    def find_compiler_span(self, json_line, src_path):
        if "message" in json_line:
            if "spans" in json_line['message']:
                for span in json_line['message']['spans']:
                    if "file_name" in span and span['file_name'] == src_path:
                        return span

        return None

    # find the span with the file path that had the issue
    def find_compiler_path(self, json_line):
        if "message" in json_line:
            if "children" in json_line['message']:
                for child in json_line['message']['children']:
                    if "spans" in child:
                        for span in child['spans']:
                            if "file_name" in span:
                                return span['file_name']

        return None

    # enable SSH key for private cargo repositories
    def enable_ssh(self, arg_git_ssh_key):
        f = open("/root/.ssh/id_rsa", "wb")
        f.write(base64.b64decode(arg_git_ssh_key))
        f.close()
        os.chmod("/root/.ssh/id_rsa", 0o600)

        subprocess.run('git config --global url."git@github.com:".insteadOf "https://github.com/"'.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run('ssh-keyscan github.com >> /root/.ssh/known_hosts'.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.config['ssh'] = True

    def __init__(self):
        # inputs
        self.config['base_dir'] = '/github/workspace'
        arg_path_glob = os.environ.get('INPUT_PATH_GLOB')
        arg_threads = os.environ.get('INPUT_THREADS')
        arg_clippy_args = os.environ.get('INPUT_CLIPPY_ARGS')
        arg_git_ssh_key = os.environ.get('INPUT_GIT_SSH_KEY')

        if arg_path_glob != None and len(arg_path_glob) > 0:
            self.config['path_glob'] = arg_path_glob

        if arg_clippy_args != None and len(arg_clippy_args) > 0:
            self.args.append(arg_clippy_args)

        if arg_threads != None and arg_threads.isdigit():
            self.config['threads'] = int(arg_threads)
        else:
            self.config['threads'] = 1

        if arg_git_ssh_key != None and len(arg_git_ssh_key) > 0:
            self.enable_ssh(arg_git_ssh_key)

        # run app
        self.run(self.config['base_dir'])

Clippy()