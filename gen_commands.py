#!/usr/bin/env python


import json
import os

from textwrap import TextWrapper

wrapper = TextWrapper(subsequent_indent='    ')
wrap = wrapper.wrap


def get_commands():
    return json.load(
        open(os.path.join(os.path.dirname(__file__), 'commands.json'))
    )


def argname(name):
    return name.lower().replace('-', '_').replace(':', '_')


def parse_arguments(command, arguments):
    args = ['self']
    doc = []
    code = ['args = ["%s"]' % command]
    for arg in arguments:
        if 'command' in arg:
            cmd = argname(arg['command'])
            if cmd in args:
                raise Exception('Command %s is already in args!' % cmd)
            cmd_default = 'None'
            if arg.get('multiple'):
                cmd_default = 'tuple()'
                if isinstance(arg['name'], list):
                    code.append('for %s in %s:' % (
                        ', '.join([argname(i) for i in arg['name']]),
                        cmd
                    ))
                    code.append(
                        '    args.append("%s")' % arg['command']
                    )
                    for i in arg['name']:
                        code.append('    args.append(%s)' % argname(i))
                else:
                    code.append('for %s in %s:' % (argname(arg['name']), cmd))
                    code.append('    args.append("%s")' % arg['command'])
                    code.append('    args.append(%s)' % argname(arg['name']))
            elif arg.get('variadic'):
                cmd_default = 'tuple()'
                code.append('if len(%s):' % cmd)
                code.append('    args.append("%s")' % arg['command'])
                if isinstance(arg['name'], list):
                    code.append('    for %s in %s:' % (
                        ', '.join([argname(i) for i in arg['name']]),
                        cmd
                    ))
                    for i in arg['name']:
                        code.append('        args.append(%s)' % argname(i))
                else:
                    code.append('    args.extend(%s)' % cmd)
            else:
                if arg.get('optional'):
                    prefix = '    '
                    code.append('if %s:' % cmd)
                else:
                    prefix = ''
                code.append(prefix + 'args.append("%s")' % arg['command'])
                if isinstance(arg['name'], list):
                    code.append(prefix + '%s = %s' % (
                        ', '.join([argname(i) for i in arg['name']]),
                        cmd
                    ))
                    for i in arg['name']:
                        code.append(prefix + 'args.append(%s)' % argname(i))
                else:
                    code.append(prefix + 'args.append(%s)' % cmd)
            if 'optional' in arg:
                args.append('%s=%s' % (cmd, cmd_default))
            else:
                args.append(cmd)
        elif arg['name'] == 'numkeys':
            # do not adding arg for numkeys argument
            assert arguments[arguments.index(arg) + 1] == {
                "name": "key",
                "type": "key",
                "multiple": True
            }
            code.append('args.append(len(keys))')
        elif isinstance(arg['name'], list):
            assert arg.get('multiple')  # makes no sense for single pairs
            if arg['name'] == [u"score", u"member"]:
                args.append('member_score_dict')
                code.append('for member, score in member_score_dict.items():')
                code.append('    args.append(score)')
                code.append('    args.append(member)')
            elif len(arg['name']) == 2 and arg['name'][1] == 'value':
                arg_name = argname(arg['name'][0])
                name = '%s_dict' % arg_name
                args.append(name)
                code.append('for %s, value in %s.items():' % (arg_name, name))
                code.append('    args.append(%s)' % arg_name)
                code.append('    args.append(value)')
            elif len(arg['name']) == 1:
                name = '%ss' % argname(arg['name'][0])
                args.append(name)
                code.append('args.extend(%s)' % name)
            else:
                raise Exception('Unknown list name group in argument '
                                'specification: %s' % arg['name'])
        elif argname(arg['name']) in args:
            raise Exception(
                'Argument %s is already in args!' % argname(arg['name'])
            )
        elif 'multiple' in arg:
            name = '%ss' % argname(arg['name'])
            if arg.get('optional'):
                args.append('%s=[]' % name)
            else:
                args.append(name)
            code.append('if isinstance(%s, basestring):' % name)
            code.append('    args.append(%s)' % name)
            code.append('else:')
            code.append('    args.extend(%s)' % name)
        elif 'enum' in arg and len(arg['enum']) == 1 and arg.get('optional'):
            name = argname(arg['name'])
            args.append('%s=False' % name)
            code.append('if %s:' % name)
            code.append('    args.append("%s")' % arg['enum'][0])
        else:
            name = argname(arg['name'])
            code.append('args.append(%s)' % name)
            if arg.get('optional') == True:
                args.append('%s=None' % name)
            else:
                args.append(name)
    args.append('callback=None')
    if len(code) > 1:
        code.append('self.send_message(args, callback)')
    else:
        code = ['self.send_message(["%s"], callback)' % command]
    return args, doc, code


name_map = {
    'del': 'delete',
    'exec': 'execute'
}


def get_command_name(command):
    name = command.lower().replace(' ', '_')
    if name in name_map:
        return name_map[name]
    else:
        return name


def get_command_code(func_name, cmd, params):

    args, args_doc, args_code = parse_arguments(
        cmd, params.get('arguments', [])
    )

    args_doc = ["    %s" % i for i in args_doc]
    args_code = ["    %s" % i for i in args_code]

    wrap = TextWrapper().wrap

    lines = []
    lines.append('def %s(%s):' % (func_name, ', '.join(args)))
    lines.append('    """')
    doc = []
    if 'summary' in params:
        doc.extend(wrap(params['summary']))
    if args_doc:
        doc.append('')
        doc.append('Arguments')
        doc.append('---------')
        doc.extend(args_doc)
    if 'complexity' in params:
        doc.append('')
        doc.append('Complexity')
        doc.append('----------')
        doc.extend(wrap(params['complexity']))
    lines.extend(['    %s' % line if line else line for line in doc])
    lines.append('    """')
    lines.extend(args_code)

    return lines


def get_class_source(class_name):
    lines = ['class %s(object):' % class_name, '']
    for cmd, params in sorted(get_commands().items()):
        for line in get_command_code(get_command_name(cmd), cmd, params):
            lines.append('    %s' % line if line else line)
        lines.append('')
    return '\n'.join(lines)


def compile_commands():
    ret = {}
    for cmd, params in sorted(get_commands().items()):
        name = get_command_name(cmd)
        lines = get_command_code(name, cmd, params)
        code = compile('\n'.join(lines), "<string>", "exec")
        ctx = {}
        exec code in ctx
        ret[name] = ctx[name]
    return ret


if __name__ == "__main__":
    with open(os.path.join(os.path.dirname(__file__), 'toredis/commands.py'), 'w') as f:
        f.write(get_class_source('RedisCommandsMixin'))
        print 'Generated commands.py'
