import os

def is_github_action():
    """Detect if we are running in a GitHub Actions environment."""
    return os.environ.get('GITHUB_WORKSPACE') is not None

def get_filepath(filename):
    """Return the appropriate filepath depending on the environment."""
    if is_github_action():
        if filename == 'status.json':
            base_path = os.environ['GITHUB_WORKSPACE']
        else:
            base_path = os.path.join(os.environ['GITHUB_WORKSPACE'], 'src')
    else:
        base_path = ''
    return os.path.join(base_path, filename)
