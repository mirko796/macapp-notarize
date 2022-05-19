from posixpath import basename
import subprocess
import argparse
import sys
import logging as log
import time
import re
import os
import stat

def parse_args(args):
    if not args:
        args = sys.argv[:]
        del args[0]
    
    credentials_required = True
    special_flags = [
        '-v',
        '--verify-only',
        '--install',
        '--uninstall'
    ]
    for s in special_flags:
        if s in args:
            credentials_required = False
            break

    parser = argparse.ArgumentParser(
        add_help=True,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-l','--log-level', type=str, 
        choices=['error','warning','info','debug'],
        default="error", help="log level")
    if "--install" not in args and "--uninstall" not in args:
        parser.add_argument('appfile',type=str)
    parser.add_argument('-u','--username', type=str, 
        help="Username (appleid)", required=credentials_required)
    parser.add_argument('-p','--password',type=str,
        help="App-specific password. For more details see https://support.apple.com/en-us/HT204397",
        required=credentials_required)
    parser.add_argument('-b','--bundle-id',type=str,
        help="Primary bundle id", required=credentials_required)
    parser.add_argument('-v','--verify-only',action='store_true')
    parser.add_argument('--install',action='store_true',
        help="Install script to /usr/bin/local")
    parser.add_argument('--uninstall',action='store_true',
        help="Uninstall script from /usr/bin/local")


    ret = parser.parse_args(args)
    return ret 

def init_logging(stderr_log_level, logger_name=None):
    logger = log.getLogger(logger_name)
    main_log_level=log.DEBUG
    log_format_str="%(asctime)s %(levelname)s %(filename)s:%(lineno)03d %(message)s"
    formatter = log.Formatter(log_format_str)
    logger.setLevel(main_log_level)
    logger.propagate = False

    handler_stderr = log.StreamHandler()
    handler_stderr.setLevel(stderr_log_level.upper())
    handler_stderr.setFormatter(formatter)
    logger.addHandler(handler_stderr)
    return logger    

def run_command(cmd_array):
    try:
        proc = subprocess.run(
            cmd_array,             
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check = True)
    except subprocess.CalledProcessError as e:
        exit_code =  e.returncode
        stdout = e.stdout
        stderr = e.stderr
    else:
        stdout = proc.stdout
        stderr = proc.stderr
        exit_code = proc.returncode
    return {
        "stdout"  : stdout.decode('utf-8'),
        "stderr"  : stderr.decode('utf-8'),
        "exitcode": exit_code
    }

def extract_upload_id(txt_output):
    """
    Output of xcrun command might differ between
    first and consequent calls for the same app
    """
    needles = [
        "The upload ID is",
        "RequestUUID = "
    ]
    ret = None
    for n in needles:
        parts = txt_output.split(n)
        if len(parts)>1:
            tmp = parts[1].strip()
            print(tmp)
            parts2 = re.split('[^0-9a-zA-Z-].', tmp)
            if len(parts2)>0:
                ret = parts2[0].strip()
                break
    return ret

# Returns upload_id
def do_upload(appfile, username, password, bundleid):
    cmd = [
        'xcrun',
        'altool',
        '-t', 'osx',
        '--primary-bundle-id', bundleid,
        '--notarize-app',
        '-u',username,
        '-p',password,
        '-f',appfile
        ]
    log.info("Executing:\r\n    %s"%(" ".join(cmd)))
    res = run_command(cmd)
    log.info("Result: %s"%str(res))
    upload_id = extract_upload_id(res['stdout']+res['stderr'])
    return upload_id

# Wait for finished
# Return codes:
#   0 - not ready
#   1 - ready
#  -1 - error
def check_is_ready(upload_id, username, password):
    cmd = [
        'xcrun',
        'altool',
        '--notarization-info',
        upload_id,
        '-u',username,
        '-p',password
        ]
    log.info("Executing:\r\n    %s"%(" ".join(cmd)))
    res = run_command(cmd)
    output = res['stdout']+"\r\n"+res['stderr']
    log.info("Output:\r\n"+output)
    lines = output.splitlines()
    ret = -1
    for l in lines:
        if "Status Message" in l and "Package Approved" in l:
            ret = 1
            break
        elif "Status: in progress" in l:
            # It is possible to have both Package Approved
            # and status in progress, so don't exit
            # right away when we find "in progress" string
            ret = 0
    log.info("Returning: %d"%ret)
    return ret

def do_wait(upload_id, username, password):
    is_ready = -1
    while True:
        is_ready = check_is_ready(upload_id, username, password)
        if is_ready!=0:
            break
        time.sleep(10)
    return is_ready

def do_staple(appfile):
    cmd = [
        'xcrun',
        'stapler',
        'staple',
        '-v',
        appfile
    ]
    log.info("Executing:\r\n    %s"%(" ".join(cmd)))
    res = run_command(cmd)
    output = (res['stdout']+"\r\n"+res['stderr'])
    ret = "The staple and validate action worked!" in output
    return ret

def do_verify(appfile):
    cmd = [
        'spctl',
        '-a',
        '-v',
        '-t',
        'install',
        appfile
    ]
    log.info("Executing:\r\n    %s"%(" ".join(cmd)))
    res = run_command(cmd)
    output = (res['stdout']+"\r\n"+res['stderr'])
    log.info("Output:\r\n"+output)
    ret = "Notarized Developer ID" in output
    log.info("Notarization status after first check: %s"%str(ret))
    if ret:
        cmd = [
            'xcrun',
            'stapler',
            'validate',
            appfile
        ]
        log.info("Executing:\r\n    %s"%(" ".join(cmd)))
        res = run_command(cmd)
        output = (res['stdout']+"\r\n"+res['stderr'])
        log.info("Output:\r\n"+output)
        ret = "The validate action worked!" in output
        log.info("Notarization status after second check: %s"%str(ret))
    return ret

def do_install_uninstall(install):
    python_exe = sys.executable
    script_path = os.path.abspath(sys.argv[0])
    basename = os.path.basename(script_path)
    script_name = "/usr/local/bin/%s"%os.path.splitext(basename)[0]
    script_content = """#!/bin/sh
%s %s "$@"
""" % (python_exe,script_path)
    log.info("Python command: %s"%python_exe)
    log.info("Python script path: %s"%script_path)
    log.info("Script path: %s"%script_name)
    log.info("Script content:\r\n%s"%script_content)
    if install:
        with open(script_name,'w') as f:
            f.write(script_content)
        st = os.stat(script_name)
        os.chmod(script_name, st.st_mode | stat.S_IEXEC)   
        print("Script installed to:\r\n\t%s"%script_name)         
    else:
        os.remove(script_name)
        print("Script uninstalled from:\r\n\t%s"%script_name)         

if __name__ == '__main__':
    time_started = time.time()
    cliargs = parse_args(None)
    log = init_logging(cliargs.log_level, __file__)
    log.info("CLI Arguments: "+str(cliargs))
    if cliargs.install or cliargs.uninstall:
        is_ok = do_install_uninstall(cliargs.install)
    else:
        file_exists = os.path.exists(cliargs.appfile)
        if not file_exists:
            raise RuntimeError("File %s does not exist"%cliargs.appfile)
        already_notarized = do_verify(cliargs.appfile)
        if not already_notarized:
            if cliargs.verify_only == False:
                upload_id = do_upload(
                    cliargs.appfile,
                    cliargs.username,
                    cliargs.password,
                    cliargs.bundle_id
                )
                if not upload_id:
                    raise RuntimeError("Failed to retrieve upload id")
                is_ok = do_wait(upload_id, cliargs.username, cliargs.password)
                if not is_ok:
                    raise RuntimeError("Something went wrong while waiting for package to be notarized")
                is_ok = do_staple(cliargs.appfile)
                if not is_ok:
                    raise RuntimeError("Something went wrong while stapling")
                print("Application notarized without errors")
            is_ok = do_verify(cliargs.appfile)
            if not is_ok:
                raise RuntimeError("Verification failed")
        print("Application verified and properly notarized")
    log.info("All done in %f seconds"%(time.time()-time_started))