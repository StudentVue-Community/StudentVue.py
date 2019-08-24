import requests
from bs4 import BeautifulSoup

from urllib.parse import urlparse, parse_qs

from datetime import datetime
import json
import re

import studentvue.models as models
import studentvue.helpers as helpers


class StudentVue:
    def __init__(self, username, password, district_domain):
        """The StudentVue scraper object.
        Args:
            username (str): The username of the student portal account
            password (str): The password of the student portal account
            district_domain (str): The domain name of your student portal
        """
        self.district_domain = urlparse(district_domain).netloc + urlparse(district_domain).path
        if self.district_domain[len(self.district_domain) - 1] == '/':
            self.district_domain = self.district_domain[:-1]

        self.session = requests.Session()

        login_page = BeautifulSoup(self.session.get(
            'https://{}/PXP2_Login_Student.aspx?regenerateSessionId=True'.format(self.district_domain)).text, 'html.parser')

        form_data = helpers.parse_form(login_page.find(id='aspnetForm'))

        form_data['ctl00$MainContent$username'] = username
        form_data['ctl00$MainContent$password'] = password

        resp = self.session.post('https://{}/PXP2_Login_Student.aspx?regenerateSessionId=True'.format(
            self.district_domain), data=form_data)

        if resp.url != 'https://{}/Home_PXP2.aspx'.format(self.district_domain):
            raise ValueError('Incorrect Username or Password')

        home_page = BeautifulSoup(resp.text, 'html.parser')

        self.id_ = re.match(
            r'ID: ([0-9]+)', home_page.find(class_='student-id').text.strip()).group(1)
        self.name = home_page.find(class_='student-name').text

        self.school_name = home_page.find(class_='school').text
        self.school_phone = home_page.find(class_='phone').text

        self.picture_url = 'https://{}/{}'.format(self.district_domain,
                                                  home_page.find(alt='Student Photo')['src'])

        self.student_guid = re.match(r'Photos/[A-Z0-9]+/([A-Z0-9-]+)_Photo\.PNG',
                                     home_page.find(alt='Student Photo')['src']).group(1)

    def get_classes(self):
        class_page = BeautifulSoup(self.session.get(
            'https://{}/PXP2_Gradebook.aspx?AGU=0'.format(self.district_domain)).text, 'html.parser')

        return self._parse_class_page(class_page)

    @staticmethod
    def _parse_class_page(class_page):
        classes_table = class_page.find('table')

        class_data = json.loads(
            re.search(r'PXP\.GBFocusData = ({.+});', class_page.find_all('script')[1].text).group(1)
        )['GradingPeriods']

        grading_periods = [
            models.GradingPeriod(
                grading_period['GU'],
                grading_period['Name']
            ) for grading_period in class_data
        ]

        return [
            models.Class(
                int(class_.find('button').text[0]),
                class_.find('button').text[3:],
                re.match(r'Room: ([a-zA-z0-9]+)', class_.find(class_='teacher-room').text.strip()).group(1),
                models.Teacher(
                    class_.find('div', class_='teacher').text,
                    helpers.parse_email(class_.find('span', class_='teacher').find('a')['href'])
                ),
                float(classes_table.find('tbody').find_all('tr', {'data-mark-gu': True})[idx].find(class_='score').text[
                      :-1]),
                grading_periods,
                int(class_['data-guid']),
                int(next(iter(class_data))['schoolID']),
                next(iter(class_data))['OrgYearGU']
            ) for idx, class_ in enumerate(classes_table.find('tbody').find_all('tr', {'data-mark-gu': False}))
        ]

    def get_assignments(self, month=datetime.now().month, year=datetime.now().year):
        calendar_page = BeautifulSoup(self.session.get(
            'https://{}/PXP2_Calendar.aspx?AGU=0'.format(self.district_domain)).text, 'html.parser')

        if month is not datetime.now().month or year is not datetime.now().year:
            form_data = helpers.parse_form(calendar_page.find(id='aspnetForm'))
            form_data['LB'] = '{}/1/{}'.format(month, year)
            calendar_page = BeautifulSoup(self.session.post(
                'https://{}/PXP2_Calendar.aspx?AGU=0'.format(self.district_domain), data=form_data).text, 'html.parser')

        return self._parse_calendar_page(calendar_page)

    @staticmethod
    def _parse_calendar_page(calendar_page):
        return [
            models.Assignment(
                re.sub(r'- Score:.+', '', assignment.text[assignment.text.index(':') + 1:]).strip(),
                assignment.text[:assignment.text.index(':')].strip(),
                int(parse_qs(assignment['href'])['DGU'][0]),
                parse_qs(assignment['href'])['GP'][0]
            ) for assignment in calendar_page.find_all('a', {'data-control': 'Gradebook_AssignmentDetails'})
        ]

    def get_student_info(self):
        student_info_page = BeautifulSoup(self.session.get(
            'https://{}/PXP2_MyAccount.aspx?AGU=0'.format(self.district_domain)).text, 'html.parser')

        return self._parse_student_info_page(student_info_page)

    @staticmethod
    def _parse_student_info_page(student_info_page):
        student_info_table = student_info_page.find('table', class_='info_tbl')

        tds = student_info_table.find_all('td')

        keys = [td.span.text for td in tds]

        for td in tds:
            td.span.clear()

        values = [td.get_text(separator='\n') for td in tds]

        return {
            k: v for (k, v) in zip(keys, values)
        }

    def get_school_info(self):
        school_info_page = BeautifulSoup(self.session.get(
            'https://{}/PXP2_SchoolInformation.aspx?AGU=0'.format(self.district_domain)).text, 'html.parser')

        return self._parse_school_info_page(school_info_page)

    @staticmethod
    def _parse_school_info_page(school_info_page):
        school_info_table = school_info_page.find('table')

        tds = school_info_table.find_all('td')

        keys = [td.span.text for td in tds]

        for td in tds:
            td.span.clear()

        values = [
            td.get_text(separator='\n') if len(td.find_all('span')) == 1 else models.Teacher(
                td.find_all('span')[1].text.strip(),
                helpers.parse_email(td.find_all('span')[1].find('a')['href'])
            )
            for td in tds
        ]

        return {
            k: v for (k, v) in zip(keys, values)
        }

    def get_image(self, fp):
        fp.write(self.session.get(self.picture_url).content)
