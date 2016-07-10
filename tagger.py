#!/usr/bin/env python3

import notmuch
import yaml
import json
import re
import os
import sys

HOMEDIR = os.getenv("HOME")
DEFAULT_CONFIG_PATH = os.path.join(HOMEDIR, ".notmuch-tagger.yml")

def pattern_match(string, pattern):
  matcher = re.compile(pattern)
  match = matcher.search(string)
  return match is not None

def validate_filters(filters):
  for filter in filters:
    fields = filter['Fields'].split(' ')
    if len(fields) == 0:
      raise ValueError('must provide at least one field to match')

    tags = filter['Tags'].split(' ')
    if len(tags) == 0 or tags == ['+inbox']:
      print(
        'WARNING: the following tags list is a no-op: "%s"' %
          filter['Tags'],
        file=sys.stderr)
    if set([x[0] for x in tags]) > set(('+', '-')):
      raise ValueError(
        'the following tags list contains unsigned tags: "%s"' %
          filter['Tags']
          )
  # do not return anything

# A tags list may contain conflicting elements, e.g. '-foo' and '+foo'.
# We handle conflicts by removing duplicate tags.  Tags appearing later
# in the list have higher priority.
def reduce_tags(tags):
  reduced_tags = []
  for tag in reversed(tags):
    tagname = tag[1:] # strip "sign"
    reduced_tagnames = [x[1:] for x in reduced_tags]
    if tagname not in reduced_tagnames:
      reduced_tags.append(tag)
  return list(reversed(reduced_tags))

def find_tags_to_apply(message, filters):
  tags_to_apply = []
  for filter in filters:
    for field in filter['Fields'].split(' '):
      value = message.get_header(field)
      if pattern_match(value, filter['Pattern']):
        tags_to_apply.extend(filter['Tags'].split(' '))
  return tags_to_apply

# add_tag() and remove_tag() must have the same footprint
def add_tag(message, tagname, dry_run=False):
  if not dry_run:
    message.add_tag(tagname)
  print(
    '%s%s: added tag "%s"' % (
      '[DRY RUN] ' if dry_run else '',
      message.get_message_id()[:20],
      tagname,
      ),
    file=sys.stderr)

def remove_tag(message, tagname, dry_run=False):
  if not dry_run:
    message.remove_tag(tagname)
  print(
    '%s%s: removed tag "%s"' % (
      '[DRY RUN] ' if dry_run else '',
      message.get_message_id()[:20],
      tagname,
      ),
    file=sys.stderr)

def apply_found_tags(tags, message, dry_run=False):
  for tag in tags:
    tag_sign = tag[0]
    tag_name = tag[1:]
    action = add_tag if tag_sign == '+' else remove_tag
    action(message, tag_name, dry_run=dry_run)

def generate_output(output_data, json_output=False):
  output = ''
  if json_output:
    output += json.dumps(output_data, indent=4)
  else:
    if output_data['total'] > 0:
      output += '\n'
      output += \
        'successfully retagged %d new messages' % output_data['total']
    else:
      output += 'no new messages found'
    output += '\n'
  return output

def main():
  # command line arguments
  new_argv = sys.argv[1:]
  dry_run = False
  if '--dry-run' in sys.argv[1:]:
    dry_run = True
    new_argv.remove('--dry-run')
  json_output = False
  if '--json-output' in sys.argv[1:]:
    json_output = True
    new_argv.remove('--json-output')
  query_string_override = None
  if len(new_argv) == 1:
    query_string_override = new_argv[0]
  elif len(new_argv) > 1:
    raise ValueError('too many arguments')

  # setup notmuch database
  db_mode = notmuch.Database.MODE.READ_WRITE
  if dry_run:
    db_mode = notmuch.Database.MODE.READ_ONLY
  db = notmuch.Database(mode=db_mode)

  # get list of messages to retag
  query_string = 'tag:new'
  if query_string_override is not None:
    query_string = query_string_override
  messages_to_retag = \
    notmuch.Query(db, query_string).search_messages()

  # load filters from configuration file
  stream = open(DEFAULT_CONFIG_PATH, 'r')
  filters = yaml.load(stream)
  stream.close()
  # we want to fail on invalid filters, so do not catch exceptions
  validate_filters(filters)

  message_counter = 0
  inbox_counter = 0
  for msg in messages_to_retag:
    msg_id = msg.get_header('Subject')
    print("processing message %s" % msg_id, file=sys.stderr)
    initial_tags = msg.get_tags()
    tags_to_apply = []
    if 'new' in initial_tags:
      # prevent this message from being processed again
      tags_to_apply.append('-new')
    tags_to_apply.extend(find_tags_to_apply(msg, filters))
    reduced_tags_to_apply = reduce_tags(tags_to_apply)
    apply_found_tags(reduced_tags_to_apply, msg, dry_run=dry_run)
    message_counter += 1
    if '-inbox' not in reduced_tags_to_apply:
      inbox_counter += 1

  output_data = {
    'inbox': inbox_counter,
    'total': message_counter,
    }
  output = generate_output(output_data, json_output=json_output)
  print(output, end='')

main()
