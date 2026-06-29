import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

class SaraminCrawler:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.salary_codes = {
            '2400만원~': '8', '2600만원~': '9', '2800만원~': '10', '3000만원~': '11',
            '3200만원~': '12', '3400만원~': '13', '3600만원~': '14', '3800만원~': '15',
            '4000만원~': '16', '5000만원~': '17', '6000만원~': '18', '7000만원~': '19',
            '8000만원~': '20', '9000만원~': '21', '1억원~': '22'
        }
        self.job_types = {
            '정규직': '1', '계약직': '2', '인턴': '4', '파견직': '6'
        }

    def search_jobs(self, keyword=None, **filters):
        jobs = []
        api_url = "https://www.saramin.co.kr/zf_user/search/get-recruit-list"
        params = {
            'searchType': 'search',
            'recruitPage': 1,
            'recruitSort': 'relation',
            'recruitPageCount': 40,
            'search_optional_item': 'y',
            'search_done': 'y',
            'preview': 'y',
            'mainSearch': 'n'
        }

        if keyword:
            params['searchword'] = keyword

        if 'job_types' in filters:
            job_type_list = [self.job_types[jt] for jt in filters['job_types'] if jt in self.job_types]
            if job_type_list:
                params['job_type'] = ','.join(job_type_list)

        if filters.get('remote_work'):
            params['work_type'] = '1'

        try:
            response = requests.get(api_url, params=params, headers=self.headers)
            response.raise_for_status()
            json_data = response.json()
            total_count = int(json_data.get('count', '0').replace(',', ''))
            max_pages = min((total_count + 39) // 40, 5)

            print(f"총 {total_count:,}개 공고 발견!")

            for page in range(1, max_pages + 1):
                params['recruitPage'] = page
                try:
                    response = requests.get(api_url, params=params, headers=self.headers)
                    json_data = response.json()

                    if json_data.get('innerHTML'):
                        soup = BeautifulSoup(json_data['innerHTML'], 'html.parser')
                        items = soup.find_all('div', class_='item_recruit')

                        for item in items:
                            job_data = self.extract_job_info(item, keyword or '전체')
                            if job_data:
                                jobs.append(job_data)

                    time.sleep(1)
                except Exception as e:
                    print(f"페이지 {page} 실패: {e}")
                    continue

        except Exception as e:
            print(f"검색 실패: {e}")
            return []

        print(f"✅ {len(jobs)}개 공고 수집 완료!")
        return jobs

    def extract_job_info(self, item, keyword):
        try:
            title_elem = item.select_one('div.area_job > h2.job_tit > a')
            title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
            href = title_elem.get('href') if title_elem else ""
            link = f"https://www.saramin.co.kr{href}" if href else ""

            company_elem = item.select_one('div.area_corp > strong.corp_name > a')
            company = company_elem.get_text(strip=True) if company_elem else "회사명 없음"

            deadline_elem = item.select_one('div.area_job > div.job_date > span.date')
            deadline = deadline_elem.get_text(strip=True) if deadline_elem else "마감일 없음"

            condition_elem = item.select('div.area_job > div.job_condition > span')
            location = "지역 없음"
            career = "경력 없음"
            education = "학력 없음"
            work_type = "근무형태 없음"

            if len(condition_elem) > 0:
                location_list = [loc.get_text(strip=True) for loc in condition_elem[0].select('a')]
                location = " ".join(location_list) if location_list else "지역 없음"

            if len(condition_elem) > 1:
                career = condition_elem[1].get_text(strip=True)
            if len(condition_elem) > 2:
                education = condition_elem[2].get_text(strip=True)
            if len(condition_elem) > 3:
                work_type = condition_elem[3].get_text(strip=True)

            return {
                'keyword': keyword,
                'title': title,
                'company': company,
                'location': location,
                'career': career,
                'education': education,
                'work_type': work_type,
                'deadline': deadline,
                'link': link,
                'crawled_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            print(f"파싱 실패: {e}")
            return None

    def save_to_csv(self, jobs):
        if not jobs:
            return None

        filename = f"마케팅_공고_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df = pd.DataFrame(jobs)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"{len(jobs)}개 공고를 {filename}에 저장했습니다.")
        return filename

    def send_email_notification(self, jobs, email_config):
        if not jobs:
            return

        subject = f"🔔 마케팅 공고 {len(jobs)}개 - {datetime.now().strftime('%m/%d')}"
        html_body = f"""
        <html>
            <body>
                <h1>🎯 마케팅 채용공고 자동 수집</h1>
                <p>총 {len(jobs)}개 공고 발견</p>
                <h2>주요 공고:</h2>
        """

        for job in jobs[:10]:
            html_body += f"""
            <div style="border:1px solid #ddd; padding:10px; margin:10px 0;">
                <strong>{job['title']}</strong><br/>
                {job['company']} | {job['location']}<br/>
                <a href="{job['link']}">보기</a>
            </div>
            """

        html_body += "</body></html>"

        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = email_config['sender_email']
            msg['To'] = email_config['receiver_email']
            msg['Subject'] = subject

            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)

            csv_filename = self.save_to_csv(jobs)
            if csv_filename and os.path.exists(csv_filename):
                with open(csv_filename, 'rb') as attachment:
                    part = MIMEApplication(attachment.read(), _subtype='csv')
                    part.add_header('Content-Disposition', 'attachment', filename=f"마케팅공고_{datetime.now().strftime('%Y%m%d')}.csv")
                    msg.attach(part)

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(email_config['sender_email'], email_config['app_password'])
            server.send_message(msg)
            server.quit()

            print("📧 이메일 발송 완료!")
        except Exception as e:
            print(f"이메일 실패: {e}")

    def run_crawler(self, email_config=None):
        print("🚀 크롤링 시작!")

        jobs = self.search_jobs(
            keyword='마케팅',
            job_types=['정규직', '계약직'],
            remote_work=True
        )

        unique_jobs = []
        seen_links = set()
        for job in jobs:
            if job['link'] not in seen_links:
                unique_jobs.append(job)
                seen_links.add(job['link'])

        print(f"✅ 총 {len(unique_jobs)}개 공고!")

        if email_config and unique_jobs:
            self.send_email_notification(unique_jobs, email_config)

        return unique_jobs

if __name__ == "__main__":
    crawler = SaraminCrawler()

    print("\n" + "="*60)
    print("🎯 마케팅 채용공고 자동화")
    print("="*60)

    email_config = {
        'sender_email': os.environ.get('EMAIL_SENDER'),
        'receiver_email': os.environ.get('EMAIL_RECEIVER'),
        'app_password': os.environ.get('EMAIL_APP_PASSWORD')
    }

    all_jobs = crawler.run_crawler(email_config)

    print(f"\n📊 최종 결과:")
    print(f"   - 총 공고: {len(all_jobs)}개")
    if all_jobs:
        print(f"   - 첫 공고: {all_jobs[0]['title']}")
