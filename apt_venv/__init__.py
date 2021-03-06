from xdg import BaseDirectory as _BaseDirectory
from shutil import rmtree as _rmtree
from subprocess import call as _call
import os as _os
import stat as _stat
from json import load as _loadJSON

from apt_venv import utils

__appname__ = 'apt-venv'

VERSION = '1.0.0'

CONFIG_LOCATIONS = [
    '/etc/apt-venv.conf',
]


class AptVenv(object):

    def _load_config_from_files(self):
        config = {}
        for fname in CONFIG_LOCATIONS:
            cf = None
            try:
                with open(fname) as fp:
                    cf = _loadJSON(fp)
            except:
                raise
            if cf is not None:
                config.update(cf)
        return config

    def __init__(self, release):
        self.release = release
        self.name = 'apt-venv'
        self.config = self._load_config_from_files()

        self.distro = None
        for distro in self.config['distributions']:
            if self.release in self.config['distributions'][distro]['releases']:
                self.distro = distro
        if not self.distro:
            base = "Release \"{}\" not valid. ".format(self.release)
            if not self.release:
                base = "No release declared. "
            all_releases = []
            for distro in sorted(self.config['distributions'].keys()):
                releases = self.config['distributions'][distro]['releases']
                all_releases.append(" [%s] %s" % (distro, ' - '.join(releases)))
            raise ValueError(base +
                             "Please specify one of:\n%s" %
                             '\n'.join(all_releases))
        self.config_path = _BaseDirectory.save_config_path(self.name)
        self.cache_path = _BaseDirectory.save_cache_path(self.name)
        self.data_path = _BaseDirectory.save_data_path(self.name)
        self.config_path = _os.path.join(self.config_path, self.release)
        self.cache_path = _os.path.join(self.cache_path, self.release)
        self.data_path = _os.path.join(self.data_path, self.release)

        self.bashrc = _os.path.join(self.config_path, "bash.rc")
        self.sourceslist = _os.path.join(self.config_path, "sources.list")
        self.aptconf = _os.path.join(self.config_path, "apt.conf")

    def exists(self):
        result = True
        for myfile in [self.bashrc, self.aptconf, self.sourceslist]:
            result = result and _os.path.isfile(myfile)
        utils.debug(1, "checking %s: %s" % (self.release, result))
        return result

    def create(self):
        utils.debug(1, "creating %s" % self.release)
        self.create_base()
        self.create_bin()
        self.create_apt_conf()
        self.create_sources_list()
        self.create_bashrc()

    def create_base(self):
        utils.create_dir(self.config_path)
        utils.create_dir(self.cache_path)

        for directory in ['var/log/apt',
                          'var/lib/apt/lists/partial',
                          'var/cache/apt/archives/partial',
                          'etc/apt/apt.conf.d',
                          'etc/apt/preferences.d',
                          'var/lib/dpkg']:
            utils.create_dir(_os.path.join(self.data_path, directory))

        for link in ['etc/apt/trusted.gpg',
                     'etc/apt/trusted.gpg.d']:
            utils.create_symlink(_os.path.join('/', link),
                                 _os.path.join(self.data_path, link))
        # touch dpkg status
        utils.touch_file(_os.path.join(self.data_path, 'var/lib/dpkg/status'))

    def create_bin(self):
        bin_dir = _os.path.join(self.data_path, 'bin')
        utils.create_dir(bin_dir)
        content = utils.get_template('FAKE_SU')
        bin_fakesu = _os.path.join(bin_dir, '__apt-venv_fake_su')
        utils.create_file(bin_fakesu, content)
        # chmod +x bin_fakesu
        _os.chmod(bin_fakesu, _os.stat(bin_fakesu).st_mode | _stat.S_IEXEC)
        for link in ['sudo', 'su']:
            utils.create_symlink(bin_fakesu, _os.path.join(bin_dir, link))

    def create_apt_conf(self):
        content = utils.get_template('apt.conf')
        content = content % {'data_path': self.data_path}
        utils.create_file(self.aptconf, content)

    def create_sources_list(self):
        content = self.config['distributions'][self.distro]['sourceslist']
        content = content % {"release": self.release}
        utils.create_file(self.sourceslist, content)
        utils.create_symlink(
            self.sourceslist,
            _os.path.join(self.data_path, "etc/apt/sources.list"))

    def create_bashrc(self):
        args = {}
        args['aptconf'] = self.aptconf
        args['data_path'] = self.data_path
        args['cache_path'] = self.cache_path
        args['release'] = self.release
        content = utils.get_template('bash.rc') % args
        utils.create_file(self.bashrc, content)

    def run(self, command=None):
        if not self.exists():
            self.create()
        bash = "bash --rcfile %s" % self.bashrc
        if command:
            bash = """bash -c "source %s ; %s" """ % (self.bashrc, command)
        utils.debug(1, "running \"%s\"" % bash)
        _call(bash, shell=True)

    def update(self):
        self.run(command="apt-get update")

    def delete(self):
        utils.debug(1, "deleting %s" % self.release)
        for directory in [self.config_path,
                          self.cache_path, self.data_path]:
            if _os.path.isdir(directory):
                utils.debug(2, "deleting dir %s" % directory)
                _rmtree(directory)
