import json
import subprocess
import os
import glob
import base64
import sys
import shlex
from concurrent.futures import ThreadPoolExecutor, wait

class Clippy:
    config = dict()
    args = [
        "cargo",
        "clippy",
        "--message-format=json",
        "--verbose"
    ]
    compiler_output = list()
    github_output = list()

    # execute the clippy command
    def exec(self, dir):
        command = self.build_command()
        print("-- COMMAND: ", command)

        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, cwd=dir)
            output = process.stdout.readlines()
            process.wait()

            print('-- Return code; ', process.returncode)

            # 101 seems to be a bug
            if (process.returncode != 0) and (process.returncode != 101):
            # if process.returncode != 0:
                print('Non-zero exit code; ', process.returncode)
                exit(1)

            return output
        except subprocess.CalledProcessError as e:
            print("Error in calling cargo; ", e.output)
            return None
        except:
            print("Unexpected error:", sys.exc_info()[0])
            print(sys.exc_info())
            return None

    # build command with args
    def build_command(self):
        gen_args = []

        if 'ssh' in self.config and self.config['ssh']:
            gen_args.append('eval $(ssh-agent -s)')
            gen_args.append('&&')
            gen_args.append('ssh-add /root/.ssh/id_rsa')
            gen_args.append('&&')

        if 'github_token' in self.config and self.config['github_token']:
            gen_args.append("CARGO_NET_GIT_FETCH_WITH_CLI=true")

        gen_args.append("HOME=/root/") # fix for HOME injection from GH runner

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

        if output == None:
            print("Failed to lint")
            exit(1)

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
        # validate we have spans
        if 'spans' not in json_line['message']:
            return None

        level = json_line['message']['level']
        message = json_line['message']['rendered']

        # likely a compiler error or dependency issue
        if not json_line['message']['spans'] and json_line['message']['level'] == 'error':
            return f"::error::{json_line['message']['message']} from {json_line['package_id']}"

        # loop through spans for this error
        for span in json_line['message']['spans']:
            # skip any non-primary spans
            if span['is_primary'] is not True:
                continue

            # assign initial path
            path = span['file_name']

            if 'path_glob' in self.config:
                path = dir.replace(self.config['base_dir'] + "/", "") + span['file_name']

            if level == "warning":
                return f"::warning file={path},line={span['line_start']},col={span['column_start']}::{message}"

            if level == "error":
                return f"::error file={path},line={span['line_start']},col={span['column_start']}::{message}"

            print("Line was missing compiler information")
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

    # enable github pat token
    def enable_github_token(self, arg_github_token):
        subprocess.run(f'git config --global url."https://clippy:{arg_github_token}@github.com/".insteadOf "https://github.com/"', shell=True)

        if 'ssh_path_rewrite' in self.config and self.config['ssh_path_rewrite']:
            subprocess.run(f'git config --global url."https://clippy:{arg_github_token}@github.com/".insteadOf "ssh://git@github.com:"', shell=True)
            subprocess.run(f'git config --global url."https://clippy:{arg_github_token}@github.com/".insteadOf "ssh://git@github.com/"', shell=True)

    # switch to a different verison of rust stable
    def switch_rust_version(self, arg_rust_version):
        subprocess.call(['rustup', 'toolchain', 'install', arg_rust_version])
        subprocess.call(['rustup', 'default', arg_rust_version])
        subprocess.call(['cargo', 'clippy', '--version'])

    def __init__(self):
        # inputs
        self.config['base_dir'] = '/github/workspace'
        arg_path_glob = os.environ.get('INPUT_PATH_GLOB')
        arg_threads = os.environ.get('INPUT_THREADS')
        arg_clippy_args = os.environ.get('INPUT_CLIPPY_ARGS')
        arg_git_ssh_key = os.environ.get('INPUT_GIT_SSH_KEY')
        arg_rust_version = os.environ.get('INPUT_RUST_VERSION')
        arg_github_pat = os.environ.get('INPUT_GITHUB_TOKEN')
        arg_ssh_path_rewrite = os.environ.get('INPUT_SSH_PATH_REWRITE')

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

        if arg_github_pat != None and len(arg_github_pat) > 0:
            if arg_ssh_path_rewrite != None and len(arg_ssh_path_rewrite) > 0:
                self.config['ssh_path_rewrite'] = True

            self.enable_github_token(arg_github_pat)
            self.config['github_token'] = True

        if arg_rust_version != None and len(arg_rust_version) > 0:
            self.switch_rust_version(arg_rust_version)

        # run app
        self.run(self.config['base_dir'])

Clippy()