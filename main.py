from typing import List, Tuple
from selenium import webdriver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.chrome.options import Options

import yaml
import time

class RegistrationBot():

    def __init__(self, options, config):
        self.browser = webdriver.Chrome(options)
        self.myuw_url = 'https://my.uw.edu/'
        self.idp_url = 'https://idp.u.washington.edu/idp/profile'
        self.registration_url = 'https://sdb.admin.uw.edu/students/uwnetid/register.asp'
        self.idp_cookies = None

        self.quarter = config['quarter']
        self.year = config['year']

        self.classHierarchy = config['slns']

        # TODO: adjust interval dynamically based on number of slns and rate limit
        self.interval = 20

    # Prompts user to log in and save cookie credentials for future login
    def uw_login(self):
        """
        Logs in to my.uw.edu to save the cookie info for future SAMl redirects
        Cookies for the idp url will automatically be saved by selenium
        """
        print('Please login with UW NetID ...')
        
        try:
            login_browser = webdriver.Chrome()
            login_browser.get(self.myuw_url)
            WebDriverWait(login_browser, 300).until(EC.url_contains(self.myuw_url))

            login_browser.get(self.idp_url)
            self.idp_cookies = login_browser.get_cookies()
            print('Login successful')
            login_browser.quit()
            
        except Exception:
            print("Login process took too long or failed.")
            login_browser.quit()
            self.browser.quit()
    
    def start(self):
        self.browser.get(self.idp_url)
        for cookie in self.idp_cookies: 
            self.browser.add_cookie(cookie)
        
        while self.classHierarchy:
            open_lecture_slns = self.get_open_lecture_slns()

            if open_lecture_slns != []:
                for lecture_sln in open_lecture_slns:
                    slns = self.get_sln_pairs(lecture_sln)
                    self.register(slns)
                    
            print()
            time.sleep(self.interval)

    # Sends a get request to urls contianing status for slns and scrape 
    # the html to get open lecture/sections
    def get_open_lecture_slns(self) -> List[int]:
        open_slns = []

        # TODO: Fix case where there class is 'Open' but no spots available
        #       (this will cause bot to repeatly register and go over registration limit)
        local_time = time.localtime()
        formatted_time = time.strftime("%H:%M:%S", local_time)

        print(formatted_time + ' Looking through slns to find open courses...')
        for lecture_sln in self.classHierarchy:
            self.browser.get(f'https://sdb.admin.uw.edu/timeschd/uwnetid/sln.asp?QTRYR={self.quarter}+{self.year}&SLN={lecture_sln}')
            status_table = self.browser.find_elements(By.CSS_SELECTOR, 'table.main')[1]
            text = status_table.get_attribute('textContent')
            if 'Open' in text:
                open_slns.append(lecture_sln)

        print('Open courses:' + str(open_slns))

        return open_slns

    # Filters the lecture sln into lecture + section sln pairs (or just lecture)
    def get_sln_pairs(self, lecture_sln) -> List[Tuple[int] | Tuple[int, int]]:
        assert lecture_sln in self.classHierarchy
        sections = self.classHierarchy[lecture_sln]

        if not sections:
            return [(lecture_sln,)]
        else:
            return [(lecture_sln, section_sln) for section_sln in sections]

    # Register and drops given slns, updates current state if successful
    def register(self, slns):
        self.browser.get(self.registration_url)

        print('Open class found, attemping to register...')
        # Register Classes
        for sln_pair in slns:
            add_slns_table = self.browser.find_element(By.CSS_SELECTOR, 'table.sps_table.update:nth-of-type(2)')

            for i, sln in enumerate(sln_pair):
                sln_input = add_slns_table.find_element(By.CSS_SELECTOR, f'tr:nth-of-type({i + 2}) input[type="text"]')
                sln_input.clear()
                sln_input.send_keys(str(sln))
            
            submit_button = self.browser.find_element(By.CSS_SELECTOR, 'input[value=" Update Schedule "]')
            submit_button.click()
        
            WebDriverWait(self.browser, 20).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.screenBlurb3')))
            result_text = self.browser.find_element(By.CSS_SELECTOR, '.screenBlurb3').text
            
            # Update list of slns to register depending on whether registration is successful
            if 'Schedule updated' in result_text:
                print('Successful registration')
                self.classHierarchy.pop(sln_pair[0])
                break

            print('Unsuccessful registration')


if __name__ == '__main__':
    # load yaml file and process command line args and configurations
    with open('config.yaml', 'r') as file:
        config = yaml.safe_load(file)

    options = Options()
    # options.add_argument("--headless")

    bot = RegistrationBot(options, config)
    bot.uw_login()
    bot.start()
    bot.browser.quit()
