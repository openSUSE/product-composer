from .runhelper import run_helper

def create_sha256_for(filename):
    with open(filename + '.sha256', 'w') as sha_file:
        # argument must not have the path
        args = [ 'sha256sum', filename.split('/')[-1] ]
        run_helper(args, cwd=("/"+os.path.join(*filename.split('/')[:-1])), stdout=sha_file, failmsg="create .sha256 file")