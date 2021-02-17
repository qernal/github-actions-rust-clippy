import json
import subprocess

class Clippy:
    args = [
        "HOME=/root",
        "cargo",
        "clippy",
        "--message-format=json"
    ]
    compiler_output = list()
    github_output = list()

    def exec(self):
        command = self.build_command()

        try:
            process = subprocess.Popen(command, stdout = subprocess.PIPE, shell=True, cwd="/github/workspace")
            return process.stdout.readlines()
        except subprocess.CalledProcessError as e:
            print("Error in calling docker; ", e.output)
            return None

    def build_command(self):
        return ' '.join(self.args)

    def run(self):
        output = self.exec()

        self.process_output(output)
        self.generate_github_output()

        for message in self.github_output:
            print(message.replace('\n', '%0A').replace('\r', '%0D'))

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

    def find_compiler_span(self, json_line, src_path):
        if "message" in json_line:
            if "spans" in json_line['message']:
                for span in json_line['message']['spans']:
                    if "file_name" in span and span['file_name'] == src_path:
                        return span

        return None

    def find_compiler_path(self, json_line):
        if "message" in json_line:
            if "children" in json_line['message']:
                for child in json_line['message']['children']:
                    if "spans" in child:
                        for span in child['spans']:
                            # print("cspan: ", span)
                            if "file_name" in span:
                                return span['file_name']

        return None

    def __init__(self):
        self.run()

Clippy()