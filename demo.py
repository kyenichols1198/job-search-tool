# -----------------------------------------------------------
# demonstrates how to scrape job postings, map companies and
# scrape misc. information such as MCAT and GRE flashcards
# email kdnichols@gmail.com
# -----------------------------------------------------------

from IPython.core.display import display, HTML
from IPython.display import display
from ipywidgets import Dropdown, widgets, Layout, HBox, Label
import re, os, json, math, requests, time, collections, folium, webbrowser
import matplotlib.pyplot as plt
from folium import plugins
from bs4 import BeautifulSoup
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
from jinja2 import Template
import numpy as np
from stop_words import get_stop_words
from nltk.tokenize import word_tokenize
  
# prints location based off csv file
def print_map(csv_name, output_name):
    df = pd.read_csv(csv_name)
    myMap = folium.Map(location=[43.073051,-89.401230], tiles='Stamen Toner', zoom_start=13)
    for i,row in df.iterrows():
        try:
            if not math.isnan(row.latitude) and not math.isnan(row.longitude):
                folium.CircleMarker((row.latitude,row.longitude), radius=3, weight=2, color=row.color, fill_color=row.color, fill_opacity=.5).add_child(folium.Popup(str(row.title) + ": "+row.url,parse_html=True)).add_to(myMap)
        except AttributeError:print(row)
    myMap.save(output_name)
    webbrowser.open_new_tab('file://'+os.getcwd()+'/'+output_name)

# method that uses cosine similarity
def cos_sim(str_x, str_y):
    # tokenize and remove stop words
    x_list = word_tokenize(str_x)
    y_list = word_tokenize(str_y)
    sw = get_stop_words('english')
    # set_x and set_y contain unique words
    set_x = {w for w in x_list if not w in sw}
    set_y = {w for w in y_list if not w in sw}
  
    y_str_vector=[]; x_str_vector=[]
    rvector = set_x.union(set_y)
    for w in rvector:
        if w in set_x: x_str_vector.append(1)
        else: x_str_vector.append(0)
        if w in set_y: y_str_vector.append(1)
        else: y_str_vector.append(0)
    cosine_value = 0
    for i in range(len(rvector)):
        cosine_value+= l1[i]*l2[i]
    h_value = float((sum(l1)*sum(l2))**0.5)
    cosine = a_value / h_value
    return cosine

# my_loc is array of of length 2 float coordinates ex. [43.073051,-89.401230]
def print_locations(csv_name, html_name, my_loc):
    # read csv file containing the company information
    df = pd.read_csv(csv_name)
    myMap = folium.Map(location=my_loc, tiles='Stamen Toner', zoom_start=13)
    # traverse rows in the excel file
    for i,row in df.iterrows():
        try:
            if not math.isnan(row.location):
                lat = row.location.split(',')[0].strip()
                long = row.location.split(',')[1].strip()
                # create the circles on the map itself
                folium.CircleMarker((lat, long),radius=3,weight=2,color=row.color,fill_color=row.color,fill_opacity=.5).add_child(folium.Popup(str(row.title) + ": "+row.url,parse_html=True)).add_to(myMap)
        except Error as e:
            print(row)
            print(e)
    # save map according to parameter
    myMap.save(html_name)
    # open the file containing the map
    webbrowser.open_new_tab('file://'+os.getcwd()+'/'+html_name)

'''
    This class uses a link from biopharmguy.com to retrieve
    biochemistry companies in the area to be displayed in a new html file
    can be used for populating locations.csv used for mapping
'''
class biopharm_scraper():
    def __init__(self, state):
        # state is two letter abbreviation for state
        link = ("https://biopharmguy.com/links/state-%s-all-geo.php" % state)
        page = requests.get(link) # retrieve biopharm page
        self.companies = [] # empty list of companies
        soup = BeautifulSoup(page.content, 'html.parser')
        # traverse table rows from biopharm
        for tr in soup.find_all('tr'):
            # temporary company dictionary
            company_rows = {}
            tds = tr.findChildren("td" , recursive=False)
            # traverse table columns
            for td in tds:
                # set company
                if td['class'] == ['company']:
                    hyper_links = td.findChildren("a" , recursive=False)
                    for link_tag in hyper_links:
                        if link_tag.getText().strip() != '':
                            company_rows['link'] = link_tag['href']
                            company_rows['title'] = link_tag.getText().strip()
                if td['class'] == ["location"] and td.getText().strip() != '':
                    company_rows['location'] = td.getText()
                if td['class'] == ["description"] and td.getText().strip() != '':
                    company_rows['description'] = td.getText()
            # add to companies list
            if len(company_rows) == 4:self.companies.append(company_rows)
    
    # html path is an html file containing {{for i in contents}}
    def display_html(self, html_path):
        myTemplate = Template(open(html_path,'r').read())
        self.html_full = myTemplate.render(content=self.companies)
        display(HTML(str(self.html_full)))
    # store companies in csv file
    def store_csv(self, csv_path):
        cols=[]; exists=True #colums
        try: cols = open(csv_path, 'r').readLine()[0].split(',')
        except:
            cols = ['title','link','location','description']
            exists=False
        with open(csv_path, 'a') as f:
            if not exists: f.write(','.join(cols)+'\n')
            for company in self.companies:
                for col in cols:
                    f.write(','.join(company[col.strip()]) +'\n')

# used scrape_indeed_skillss to check if hmtl tag visible
def visible(element):
    if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
        return False
    elif re.match('<!--.*-->', str(element)):
        return False
    elif element == u'\xa0':
        return False
    return True

'''
    This function is used to compile study posts by link
    and returns a list of job postings consisting of link and title
    skills are retrieved and can be graphed by frequency amongst postings
    Inspired by: https://jessesw.com/Data-Science-Skills/
'''
class scrape_indeed():
    # class uses job title to scrape indeed posts
    def __init__(self,fname, kws, job_title):
        self.fname = fname
        self.job_title =job_title
        self.kws =kws
        if input("Does "+ self.fname + " Exist? (y/n)") == 'y':
            self.trav_pages()
    
    # traverse each page
    def trav_pages(self):
        skills_lower = [s.lower() for s in self.kws]
        skills = []; post_words = []
        stop_words = get_stop_words('english')
        post_data = self.scrape_page()
        for i in range(len(post_data)):
            try:
                url = 'http://www.indeed.com/rc/clk?jk='+ post_data.iloc[i, 3]
                job_page = requests.get(url)
            except:
                skills.append(None)
                post_words.append(None)
                continue
            soup = BeautifulSoup(job_page.content,'html.parser')
            texts = soup.findAll(text=True)
            visible_texts = list(filter(visible, texts))
            string = re.sub('[^a-z.+3]', ' ', ' '.join(visible_texts).lower())
            string = re.sub('\.\s+', ' ', string)
            words = str.split(string)
            words = set(words) - set(stop_words)
            required_skills = list(words.intersection(skills_lower))
            skills.append(required_skills)
            post_words.append(list(words))
            time.sleep(.2)
        post_data['skills'] = skills
        post_data['words'] = post_words
        post_data.to_csv(self.fname)
    
    # print frequency of skills
    def print_skills(self, img_name):
        df = pd.read_csv(self.fname)
        results = {}
        for i,row in df.iterrows():
            tokens = re.findall(r"'(\w+)'", row.skills)
            if len(tokens) > 0:
                for token in tokens:
                    if token in list(results):
                        results[token]+=1
                    else:
                        results[token]=1
        skills=[]; skill_scores=[]
        for result in results:
            skills.append(result)
            skill_scores.append(results[result])
        fig = plt.figure()
        #fig.set_title(title)
        ax = fig.add_axes([0,0,4,2])
        ax.bar(skills,skill_scores)
        plt.show()
        plt.savefig(img_name)

    # scrapes each page
    def scrape_page(self):
        url = 'http://www.indeed.com/jobs?q="%s"&start='% '+'.join(self.job_title.split(' '))
        page = requests.get(url)
        bs_tree = BeautifulSoup(page.content, 'html.parser')
        # number of pages and job posts
        n_pages = 0; n_jobs = 0
        for token in str(bs_tree.find(id = 'searchCount').getText()).split(' '):
            if ',' in token:
                temp_arr = token.split(',')
                n_jobs = int(temp_arr[1])
                n_pages = int(temp_arr[0])
                break
        # scrape all jobs title, company, location, id, and link
        base_url = 'http://www.indeed.com'
        # intended to be list of dictionaries
        post_title = []
        post_company = []; post_loc = []
        post_id = []; post_link = []
        for i in range(n_pages): #do range(num_pages) if you want them all
            temp_url = url + str(i*10)
            page = requests.get(temp_url)
            bs_tree = BeautifulSoup(page.content, 'html.parser')
            divs = bs_tree.findAll('div')
            post_div = [jp for jp in divs if not jp.get('class') is None
                    and 'row' in jp.get('class')]
            for post in post_div:
                id = post.get('data-jk', None)
                title = post.find_all('a', {'data-tn-element': 'jobTitle'})
                company = post.find_all('span', {'class': 'company'})
                location = post.find_all('span', {'class': 'location'})
                post_title.append(str.strip(title[0].text) if title else None)
                post_company.append(str.strip(company[0].text) if company else None)
                post_loc.append(str.strip(location[0].text) if location else None)
                post_id.append(id)
                post_link.append(base_url + '/rc/clk?jk=' + id)
                # print(len(post_link), len(post_title), len(post_company), len(post_loc))
            time.sleep(.25)
        post_data = pd.DataFrame({'post_title': post_title,
                           'post_company' : post_company,
                           'post_loc' : post_loc,
                           'post_id' : post_id,
                           'post_link': post_link})
        # remove duplicates
        post_data = post_data.drop_duplicates()
        return post_data
        
