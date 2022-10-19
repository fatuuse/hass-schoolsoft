from bs4 import BeautifulSoup
from datetime import datetime, date
import requests, re, logging, json
from itertools import product
import argparse

class AuthFailure(Exception):
    """In case API authentication fails"""
    pass


class SchoolSoft(object):
    """SchoolSoft Core API (Unofficial)"""

    def __init__(self, school, username, password, usertype = 1):
        """
        school = School being accessed
        username = Username of account being logged in
        password = Password of account being logged in
        usertype = Type of account;
        0 = teacher, 1 = student, 2 = parent
        """
        self.school = school

        self.username = username
        self.password = password
        self.usertype = usertype

        self.cookies = {}

        _login_page_re = r"https://sms(\d*).schoolsoft.se/%s/html/redirect_login.htm"
        self._login_page_re = re.compile(_login_page_re % school)

        # Might not be needed, still gonna leave it here
        self.login_page = "https://sms.schoolsoft.se/{}/jsp/Login.jsp".format(school)

    def try_get(self, url, attempts = 0):
        """
        Tries to get URL info using
        self.username && self.password

        Mainly for internal calling;
        however can be used to fetch from pages not yet added to API.
        """
        logging.debug("Try get: " + url)
        r = requests.get(url, cookies=self.cookies)

        login_page_match = self._login_page_re.match(r.url)
        if login_page_match:
            server_n = login_page_match.groups()
            logging.debug("Server number: " + str(server_n))

            if attempts < 1:
                # Sends a post request with self.username && self.password
                loginr = requests.post(self.login_page, data = {
                    "action": "login",
                    "usertype": self.usertype,
                    "ssusername": self.username,
                    "sspassword": self.password
                    }, cookies=self.cookies, allow_redirects=False)

                # Saves login cookie for faster access after first call
                self.cookies = loginr.cookies
                logging.debug('Save cookie in memory')

                return self.try_get(url, attempts+1)
            else:
                raise AuthFailure("Invalid username or password")
                logging.error("Invalid username or password")
        else:
            logging.debug("SchoolSoft logged in")
            return r

    def fetch_settings(self):
        """
        Fetches settings
        """
        settings_html = self.try_get("https://sms.schoolsoft.se/{}/jsp/student/right_parent_pwdadmin.jsp".format(self.school))
        settings = BeautifulSoup(settings_html.text, "html.parser")

        students_id = []
        students_name= []

        for a in settings.find_all("a", href=re.compile("right_public_parent_rss")):
          logging.debug("RSS-link: " + str(a['href']))

          try:
            keys = re.split('[?&]',a['href'])
            matching = [s for s in keys if "key=" in s]
            students_id.append(matching[0].split('=')[1])
          except:
            logging.debug("No student in list")

          try:
            students_name.append(a.getText().strip())
          except:
            logging.debug("No name of student in list")

          students=[students_id,  students_name]
        return students

    def fetch_lunch_menu(self, student=""):
        """
        Fetches the lunch menu for the entire week
        Returns an ordered list with days going from index 0-4
        This list contains all the food on that day
        """
        menu_html = self.try_get(
            "https://sms.schoolsoft.se/{}/jsp/student/right_student_lunchmenu.jsp?menu=lunchmenu&student={}". \
            format(self.school, student)
            )
        menu = BeautifulSoup(menu_html.text, "html.parser")

        lunch_menu = []
        lunch_menu_grouped = []
        

        for div in menu.find_all("td", {"style": "word-wrap: break-word"}):
            food_info = div.get_text(separator=u"<br/>")
            logging.debug("Menu raw:" + food_info)
            #food_info = food_info.split(u"<br/>")
            food_info = food_info.replace("<br/>"," ")
            lunch_menu.append(food_info)
        
        logging.debug("Menu count: " + str(len(lunch_menu) ))
        if len(lunch_menu) > 5:
            for day in range(0,len(lunch_menu),2):
          	# step of 2
              lunch_menu_grouped.append([lunch_menu[day],lunch_menu[day+1]])
        else:
            for day in range(0,len(lunch_menu),1):
              lunch_menu_grouped.append(lunch_menu[day])

        return lunch_menu_grouped

    def fetch_schedule(self, student=""):
        """
        Fetches the schedule of logged in user
        Returns an (not currently) ordered list with days going from index 0-4
        This list contains all events on that day
        """
        

        schedule_html = self.try_get(
            "https://sms.schoolsoft.se/{}/jsp/student/right_student_schedule.jsp?menu=schedule&student={}". \
            format(self.school, student)
            )
        schedule = BeautifulSoup(schedule_html.text, "html.parser")
        
        
        
        table = schedule.find("table", { "class" : "tab_dark" })
        
        rows=table.findAll("tr")
        row_lengths=[len(r.findAll(['th','td'])) for r in rows]
        ncols=max(row_lengths)+15
        nrows=len(rows)
        data=[]
        #print("rows: ",nrows)
        #print("cols: ",ncols)
        
        for i in range(nrows):
            rowD=[]
            for j in range(ncols):
                rowD.append('')
            data.append(rowD)
        
        for i in range(len(rows)):
            row=rows[i]
            rowD=[]
            cells = row.findAll(["td","th"])
            for j in range(len(cells)):
                cell=cells[j]
                
                #lots of cells span cols and rows so lets deal with that
                cspan=int(cell.get('colspan',1))
                rspan=int(cell.get('rowspan',1))
                l = 0
                for k in range(rspan):
                    # Shifts to the first empty cell of this row
                    while data[i + k][j + l]:
                        l += 1
                    for m in range(cspan):
                        cell_n = j + l + m
                        row_n = i + k
                        # in some cases the colspan can overflow the table, in those cases just get the last item
                        cell_n = min(cell_n, len(data[row_n])-1)
                        if (k == 0 and m == 0):
                            data[row_n][cell_n] += cell.text.replace('\r\n',' ').replace('\xa0','')
                        else:
                            data[row_n][cell_n] += "-"
                        #data[row_n][cell_n] += cell.text.replace('\n','')
                        

            data.append(rowD)

        # Char to use as empty
        pattern = re.compile('^[- ]+$')
        
        # Del empty lists
        for row in reversed(range(len(data))):
            #print(data[row])
            if (len(data[row]) == 0):
                del(data[row])
        
        # Del empty rows
        for row in reversed(range(len(data))):
            del_row = True
            for col in reversed(range(len(data[row]))):
                    if not bool(re.search(pattern, data[row][col])) and not data[row][col] == "":
                        del_row = False
            if (del_row == True):
                    try:
                        del(data[row])
                    except IndexError:
                        pass
        
        # Del empty cols
        for col in reversed(range(len(data[0]))):
            del_col = True
            for row in reversed(range(len(data))):
                    #print(row,col,data[row][col])
                    if not bool(re.search(pattern, data[row][col])) and not data[row][col] == "":
                        del_col = False
                    else:
                        data[row][col] = ""
            if (del_col == True):
                for row in reversed(range(len(data))):
                    try:
                        #print("del: ",row,col)
                        del(data[row][col])
                    except IndexError:
                        #print("no del: ",row,col)
                        pass
                
        
        full_schedule = []
        
        for day in range(len(data[0])):
            full_schedule.append(day)
            full_schedule[day] = []
            for row in range(len(data)):
                if data[row][day] != "":
                    #print(data[row])
                    full_schedule[day].append(re.sub(r'(.*?)(\d+\:\d+\-\d+\:\d+)(.*?)', r'\1 \2 \3', data[row][day]))

        
        del(full_schedule[0]) # del first sets, only half hours
        
        #print(full_schedule)
        
        return full_schedule
            
        """
        full_schedule = []

        for a in schedule.find_all("a", {"class": "schedule"}):
            info = a.find("span")

            info_pretty = info.get_text(separator=u"<br/>").replace('\r\n', '').split(u"<br/>")
            #info_pretty = [item.encode("utf-8") for item in info_pretty]
            #print(info_pretty)
            full_schedule.append(info_pretty)

        full_schedule_ordered = []
        # Reorder schedule, 5th element
        table = schedule.find("div", {"id": "schedule_cont_content"}).table
        
        
        return full_schedule
        """

    def fetch_preschool_schedule(self, student=""):
        """
        Fetches times for parent times
        """
        preschool_schedule_html = self.try_get(
            "https://sms.schoolsoft.se/{}/jsp/student/right_parent_preschool_schedule_new.jsp?student={}&fromdate={}". \
            format(self.school, student, date.today().strftime("%Y-%m-%d"))
            )
        

        schedule = BeautifulSoup(preschool_schedule_html.text, "html.parser")

        preschool_schedule = []

        for td in schedule.find("form", {"id": "times"}).find_all("tr")[1].find_all("td", {"class": "value"}):

          if td.find("input"):
            time = [td.find_all("input")[0].get('value'), td.find_all("input")[1].get('value')]
          else:
            time = td.get_text().split(u" - ")
          logging.debug("Preschool time: {}".format(' '.join(map(str, time))))
          preschool_schedule.append(time)

        return preschool_schedule
        
    def fetch_info(self, student=""):
        """
        Fetches student main page
        needed to get preschool schedule 

        """
        info_html = self.try_get(
            "https://sms.schoolsoft.se/{}/jsp/student/top_student.jsp?student={}". \
            format(self.school, student)
            )
        return None

if __name__ == "__main__":
  # Test stuff
  logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)
  try:
    import testkeys
    api = SchoolSoft(testkeys.school, testkeys.username, testkeys.password, testkeys.usertype)
  except ImportError:
    logging.debug("No testkeys")
    try:
      parser = argparse.ArgumentParser()
      parser.add_argument("-s", "--school", required = True, help = "School parameter eg. abcd in https://sms.schoolsoft.se/abcd/")
      parser.add_argument("-u", "--username", required = True, help = "Username")
      parser.add_argument("-p", "--password", required = True, help = "Password")
      parser.add_argument("-t", "--usertype", type=int, default=2, help = "User type 0 = teacher, 1 = student, 2 = parent")
      parser.add_argument("-l", "--loglevel", type=str, default="warning", help = "log level")
      args = parser.parse_args()

      levels = {
        'critical': logging.CRITICAL,
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
      }
      log_level = levels.get(args.loglevel.lower())
      
      logging.getLogger().setLevel(log_level)
      
      api = SchoolSoft(args.school, args.username, args.password, args.usertype)
    except argparse.ArgumentError:
      logging.debug("No args")
      exit()


  day_names = ['Måndag','Tisdag','Onsdag','Torsdag','Fredag','Lördag','Söndag']


  weekday = int(datetime.today().weekday())
  current_h = int((datetime.now()).hour)
  
  
  if current_h > 16 and weekday < 4 :
     weekday = weekday+1
  
  settings = api.fetch_settings()
  #print(settings)
  if weekday < 5:
    output = dict(
      updated = int(datetime.timestamp(datetime.now())),
      icon = "mdi:school",
      day = day_names[weekday],  #datetime.today().strftime('%A'),
      )
      
    if len(settings) < 1:
      #raise ValueError("No students")
      logging.debug("No students")
    else:
      for i in range(1,len(settings[0])+1):
        setting_i = i-1
        logging.debug("Fetch info student " + str(i) + ' of ' + str(len(settings[0])) +' with id ' + settings[0][setting_i])
        output.update(
          {'student_'+ str(i) +'_id':settings[0][setting_i],
          'student_'+ str(i) :settings[1][setting_i],
          'info_'+ str(i) :api.fetch_info(student=settings[0][setting_i]), # no info, needed to change student
          'preschool_'+ str(i) :api.fetch_preschool_schedule(student=settings[0][setting_i])[weekday],
          'schedule_'+ str(i) :api.fetch_schedule(student=settings[0][setting_i]),
          'meals_' + str(i) :api.fetch_lunch_menu(student=settings[0][setting_i])}
          )

    if len(output["meals_1"]) >= weekday and len(output["meals_1"]) != 0:
    	output["meal"] = output["meals_1"][weekday]
  else:
    output = dict(
      updated = int(datetime.timestamp(datetime.now())),
      icon = "mdi:school",
      day = datetime.today().strftime('%A'),
      meal= ""
      )
    if len(settings) < 1:
      #raise ValueError("No students")
      logging.debug("No students")
    else:
      for i in range(1,len(settings[0])+1):
        setting_i = i-1
        logging.debug("Fetch info student " + str(i) + ' of ' + str(len(settings[0])) +' with id ' + settings[0][setting_i])
        output.update(
          {'student_'+ str(i) +'_id':settings[0][setting_i],
          'student_'+ str(i) :settings[1][setting_i],
          'info_'+ str(i) :api.fetch_info(student=settings[0][setting_i]), # no info, needed to change student
          'preschool_'+ str(i) :'',
          'schedule_'+ str(i) :api.fetch_schedule(student=settings[0][setting_i])}
          )
  

  #print(json.dumps(output, ensure_ascii=False).encode('utf8'))
  print(json.dumps(output, ensure_ascii=False))
  

  """
  Eg calls
  settings = api.fetch_settings()
  lunch = api.fetch_lunch_menu(student=123)
  schedule = api.fetch_schedule(student=123)
  preschool_schedule = (api.fetch_preschool_schedule(students=123)
  """
  quit()
