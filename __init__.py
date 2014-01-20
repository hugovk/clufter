# -*- coding: UTF-8 -*-
version = '0.1'
copyright = """\
Copyright 2014 Red Hat, Inc.
Licensed under GPLv2
""".rstrip()
author = "Jan Pokorný <jpokorny @at@ Red Hat .dot. com>"

metadata = (version, copyright, author)


def version_line(package='clufter', sep=', '):
    return (sep.join((package,) + metadata)
            .replace(' \n', '\n')
            .replace(' @at@ ', '@')
            .replace(' .dot. ', '.')
            .replace('@Red Hat.', '@redhat.'))
