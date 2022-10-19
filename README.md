# hass-schoolsoft
Home Assistant sensor for Swedish SchoolSoft school management system. 


## Setup in Home Assistant
```
- platform: command_line
  name: SchoolSoft
  json_attributes:
  - updated
  - icon
  - meal
  - meals_1
  - student_1
  - student_2
  - student_3
  - preschool_1
  - preschool_2
  - preschool_3
  - schedule_1
  - schedule_2
  scan_interval: 21600 #6h
  command_timeout: 30
  command: python3 /config/script/schoolsoft.py -s school -u user -p password
  value_template: '{{ value_json.day | default("") }}'
```
