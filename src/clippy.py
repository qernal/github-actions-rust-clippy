import json
import subprocess
import os
import glob
import base64

class Clippy:
    config = dict()
    args = [
        "HOME=/root",
        "cargo",
        "clippy",
        "--message-format=json"
    ]
    compiler_output = list()
    github_output = list()

    # execute the clippy command
    def exec(self, dir):
        command = self.build_command()

        try:
            process = subprocess.Popen(command, stdout = subprocess.PIPE, shell=True, cwd=dir)
            output = process.stdout.readlines()
            process.wait()

            if process.returncode != 0:
                print('Non-zero exit code; ', process.returncode)
                exit(1)

            return output
        except subprocess.CalledProcessError as e:
            print("Error in calling docker; ", e.output)
            return None

    # build command with args
    def build_command(self):
        ssh_args = []

        if 'ssh' in self.config and self.config['ssh']:
            ssh_args = 'eval $(ssh-agent -s) && ssh-add /root/.ssh/id_rsa'.split(" ")
            ssh_args.append('&&')

        return ' '.join(ssh_args + self.args)

    # main handler
    def run(self, dir = "/github/workspace"):
        if 'path_glob' in self.config:
            for path in glob.glob("/".join([dir, self.config['path_glob']])):
                if os.path.exists("".join([path, "Cargo.toml"])):
                    print('Globbed path, found Cargo at: ', path)
                    self.compile(path)
        else:
            self.compile(dir)

        for message in self.github_output:
            print(message.replace('\n', '%0A').replace('\r', '%0D'))

    # compile the command and output together
    def compile(self, dir):
        output = self.exec(dir)
        self.process_output(output)
        self.generate_github_output()

    # process clippy output
    def process_output(self, output):
        for line in output:
            try:
                line = line.strip()
                json_line = json.loads(line)

                if "reason" in json_line:
                    if json_line['reason'] == "compiler-message":
                        # we'll accept this and add it to our compiler output
                        self.compiler_output.append(json_line)
            # not a json line so, we'll skip
            except AttributeError:
                print('Skipping line in output; ', line)
            except ValueError:
                print('Skipping line in output; ', line)

    # convert compiler output to github output
    def generate_github_output(self):
        for json_line in self.compiler_output:
            gh_output = self.line_compiler_to_gh(json_line)

            if gh_output != None:
                self.github_output.append(gh_output)

    # convert each compiler line to a valid github warning or error
    def line_compiler_to_gh(self, json_line):
        level = json_line['message']['level']
        path = self.find_compiler_path(json_line)
        message = json_line['message']['rendered']
        span = self.find_compiler_span(json_line, path)

        if path == None or span == None:
            return None

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
        arg_path_glob = os.environ.get('INPUT_PATH_GLOB')
        arg_clippy_args = os.environ.get('INPUT_ARGS')
        arg_git_ssh_key = os.environ.get('INPUT_GIT_SSH_KEY')

        if arg_path_glob != None:
            self.config['path_glob'] = arg_path_glob

        if arg_git_ssh_key != None:
            self.enable_ssh(arg_git_ssh_key)

        # run app
        self.run()

Clippy()