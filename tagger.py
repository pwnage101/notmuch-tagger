#!/usr/bin/env python3

import notmuch
import yaml
import re

NM_DATABASE_PATH = "/home/sankey/mail"

def pattern_match(string, pattern):
  matcher = re.compile(pattern)
  match = matcher.search(string)
  return match is not None

def find_tags_to_apply(message, filters):
  for filter in filters:
    for field in filter['Fields'].split(' '):
      value = message.get_header(field)
      if pattern_match(value, filter['Pattern']):
        return filter['Tags'].split(' ')
  return []

def apply_found_tags(tags, message):
  for tag in tags:
    tag_sign = tag[0]
    tag_name = tag[1:]
    if tag_sign == '+':
      message.add_tag(tag_name)
#      print('add tag "%s"' % tag_name)
    elif tag_sign == '-':
      message.remove_tag(tag_name)
#      print('remove tag "%s"' % tag_name)
    else:
      raise

def main():
  # get list of new messages
  db = notmuch.Database(
         NM_DATABASE_PATH,
         create=False,
         mode=notmuch.Database.MODE.READ_WRITE)
  msgs = notmuch.Query(db, 'tag:new').search_messages()

  # load filters from configuration file
  stream = open('filters.yml', 'r')
  filters = yaml.load(stream)

  for msg in msgs:
    msg_id = msg.get_header('Subject')
    print("processing message %s" % msg_id)
    tags = msg.get_tags()
    if 'new' in tags:
      msg.remove_tag('new')
#      print('remove tag "new"')
      msg.add_tag('inbox')
#      print('add tag "inbox"')
    tags_to_apply = find_tags_to_apply(msg, filters)
    apply_found_tags(tags_to_apply, msg)

main()
