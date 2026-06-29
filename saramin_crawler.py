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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 파라미터들을 딕셔너리로 정리!
        self.salary_codes = {
            '2400만원~': '8', '2600만원~': '9', '2800만원~': '10', '3000만원~': '11',
            '3200만원~': '12', '3400만원~': '13', '3600만원~': '14', '3800만원~': '15',
            '4000만원~': '16', '5000만원~': '17', '6000만원~': '18', '7000만원~': '19',
            '8000만원~': '20', '9000만원~': '21', '1억원~': '22'
        }
        
        self.company_types = {
            '대기업': 'scale001', '중견기업': 'scale003', '중소기업': 'scale004',
            '스타트업': 'scale005', '외국계': 'foreign', '코스닥': 'kosdaq',
            '공사/공기업': 'public', '연구소': 'laboratory', '교육기관': 'school',
            '금융기업': 'banking-organ'
        }
        
        self.job_types = {
            '정규직': '1', '계약직': '2', '병역특례': '3', '인턴': '4',
            '아르바이트': '5', '파견직': '6', '해외취업': '7', '위촉직': '8',
            '프리랜서': '9', '교육생': '12', '파트타임': '14', '전임': '15'
        }
        
        self.work_days = {
            '주5일': 'wsh010', '주6일': 'wsh030', '주3일/격일': 'wsh040',
            '유연근무제': 'wsh050', '면접후결정': 'wsh090'
        }

    def search_jobs(self, keyword=None, **filters):
        """실제 api 엔드포인트 사용한 검색"""

        jobs = []

        # 실제 API URL
        api_url = "https://www.saramin.co.kr/zf_user/search/get-recruit-list"

        # API 파라미터 (Network 탭에서 발견한 것들)
        params = {
            'searchType': 'search',
            'recruitPage': 1,     # 페이지네이션
            'recruitSort': 'relation',   # 정렬기준(관련도순)
            'recruitPageCount': 40,    # 한 폐이지에 보이는 개수
            'search_optional_item': 'y',
            'search_done': 'y',
            'panel_count': 'y',
            'preview': 'y',
            'mainSearch': 'n'
        }

        # 검색어
        if keyword:
            params['searchword'] = keyword

        # 고급 필터 적용
        self._apply_filters(params, filters)

        try:
            response = requests.get(api_url, params=params, headers=self.headers)
            response.raise_for_status()

            # JSON 응답 파싱 : 응답은 json 형태이기때문 '{"count":"283","innerHTML":"<div>...</div>"}'
            json_data = response.json()

            # 전체 공고 수 계산
            total_count = int(json_data.get('count', '0').replace(',', ''))

            # 공고가 많으면 5페이지만 크롤링 
            max_pages = min((total_count + 39) // 40, 5)

            print(f"총 {total_count:,}개 공고 발견! {max_pages}페이지 크롤링 예정")

            for page in range(1, max_pages + 1):
                print(f"📄 {page}/{max_pages} 페이지 수집 중...")

                params['recruitPage'] = page

                try: 
                    # 각 페이지마다 새로 API 호출
                    response = requests.get(api_url, params=params, headers=self.headers)
                    response.raise_for_status()
                    json_data = response.json()  # 해당 페이지 데이터

                    if json_data.get('innerHTML'):
                        # 채용공고 추출
                        soup = BeautifulSoup(json_data['innerHTML'], 'html.parser')
                        json_itmes = soup.find_all('div', class_='item_recruit')

                        if not json_itmes:
                            print(f"페이지 {page}에서 공고를 찾을 수 없습니다.")
                            break

                        print(f"총 └─ {len(json_itmes)}개 수집")

                        for item in json_itmes:
                            job_data = self.extract_job_info_from_api(item, keyword or '전체')
                            if job_data:
                                jobs.append(job_data)
                    else:
                        print(f"페이지 {page}에서 데이터를 받지 못했습니다.")
                        break

                    time.sleep(1)  # 서버 부하 방지

                except Exception as e:
                    print(f"❌ 페이지 {page} 크롤링 실패: {e}")
                    continue
        
        except Exception as e:
            print(f"❌ 초기 데이터 로딩 실패: {e}")
            return []
        
        print(f"✅ '{keyword or '전체'}' 총 {len(jobs)}개 공고 수집 완료!")
        return jobs
    
    def _apply_filters(self, params, filters):
        """필터들을 파라미터에 적용"""

        # 연봉 필터
        if 'salary_min' in filters:
            if filters['salary_min'] in self.salary_codes:
                params['sal_min'] = self.salary_codes[filters['salary_min']]

        # 회사 규모/유형
        if 'company_types' in filters:
            company_list = []
            for company_type in filters['company_types']:
                if company_type in self.company_types:
                    company_list.append(self.company_types[company_type])
            if company_list:
                params['company_type'] = ','.join(company_list)

        # 고용 형태
        if 'job_types' in filters:
            job_type_list = []
            for job_type in filters['job_types']:
                if job_type in self.job_types:
                    job_type_list.append(self.job_types[job_type])
            if job_type_list:
                params['job_type'] = ','.join(job_type_list)

        # 근무 유형
        if 'work_days' in filters:
            work_day_list = []
            for work_day in filters['work_days']:
                if work_day in self.work_days:
                    work_day_list.append(self.work_days[work_day])
            if work_day_list:
                params['work_day'] = ','.join(work_day_list)

        # 재택근무 가능 유형
        if filters.get('remote_work', False):
            params['work_type'] = '1'

        # 제외 키워드
        if 'exclude_keywords' in filters:
            params['exc_keyword'] = ','.join(filters['exclude_keywords'])

        
    def extract_job_info_from_api(self, item, keyword):
        """API에서 받은 HTML 구조에 맞게 정보 추출"""
        try:
            # 공고 제목 및 링크
            title_elem = item.select_one('div.area_job > h2.job_tit > a')
            title = title_elem.get_text(strip=True) if title_elem else print("공고명 못찾음❌❌")

            # 링크 처리 (상대경로 → 절대경로 변환)
            href = title_elem.get('href') if title_elem else ""
            link = f"https://www.saramin.co.kr{href}" if href else ""
            
            # 회사명
            company_elem = item.select_one('div.area_corp > strong.corp_name > a')
            company = company_elem.get_text(strip=True) if company_elem else print("회사명 찾지 못함❌❌")

            # 마감일
            deadline_elem = item.select_one('div.area_job > div.job_date > span.date')
            deadline = deadline_elem.get_text(strip=True) if deadline_elem else print("마감일 찾지 못함❌❌")

            # 위치, 경력 정보
            condition_elem = item.select('div.area_job > div.job_condition > span')

            # 기본값 설정
            location = "지역 없음"  
            career = "경력 없음"
            education = "학력 없음"  
            work_type = "근무형태 없음"

            # 안전하게 인덱스 확인 후 추출
            if len(condition_elem) > 0:
                location_elem = condition_elem[0].select('a')
                location_list = [loc.get_text(strip=True) for loc in location_elem]
    
                if len(location_list) >= 2:
                    # "서울 강남구" 형태로
                    location = " ".join(location_list)
                elif len(location_list) == 1:
                    # "서울" 같이 하나만 있는 경우
                    location = location_list[0]
                else:
                    location = "지역 없음"

            # 경력 
            if len(condition_elem) > 1:
                career_elem = condition_elem[1]
                career = career_elem.get_text(strip=True)

            # 학력
            if len(condition_elem) > 2:
                edu_elem = condition_elem[2]
                education = edu_elem.get_text(strip=True)

            # 근무 조건
            if len(condition_elem) > 3:
                work_type_elem = condition_elem[3]
                work_type = work_type_elem.get_text(strip=True)

            # 공고 ID 추출
            rec_idx = item.get('value', '')

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
                'rec_idx': rec_idx,
                'crawled_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"⚠️ 공고 정보 추출 실패 : {e}")
            print(f"⚠️ 문제 공고 HTML 구조: {item}")
            return None


    def save_to_csv(self, jobs, filename=None):
        """결과를 csv로 저장"""
        if not jobs:
            print("저장할 데이터가 없습니다.")
            return
        
        if not filename:
            # 아무런 경로가 없으면 현재 이 python 파일이 있는 곳에 저장됩니다.
            filename = f"사람인_공고_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"   

            # 원하는 경로와 파일명 지정 가능합니다.
            # filename = f"./output/사람인_공고_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        df = pd.DataFrame(jobs)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"{len(jobs)}개 공고를 {filename}에 저장하였습니다.")
        return filename
    
    def send_email_notification(self, jobs, email_config):
        """이메일로 공고 알림"""
        if not jobs:
            return
        
        # 이메일 내용 생성
        subject = f"🔔 새 마케팅 채용공고 {len(jobs)}개 발견! - {datetime.now().strftime('%m/%d')}"
        
        # HTML 템플릿
        html_body = f"""
        <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: 'Apple SD Gothic Neo', Arial, sans-serif; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            color: white; padding: 20px; text-align: center; }}
                    .job-item {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; 
                            border-radius: 8px; background: #fafafa; }}
                    .job-title {{ font-size: 18px; font-weight: bold; color: #2c3e50; }}
                    .company {{ color: #e74c3c; font-weight: bold; margin: 5px 0; }}
                    .details {{ color: #7f8c8d; font-size: 14px; margin: 5px 0; }}
                    .btn {{ background: #3498db; color: white; padding: 8px 16px; 
                        text-decoration: none; border-radius: 4px; display: inline-block; }}
                    .summary {{ background: #ecf0f1; padding: 15px; margin: 20px 0; border-radius: 8px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🎯 마케팅 채용공고 자동 수집 결과</h1>
                    <p>{datetime.now().strftime('%Y년 %m월 %d일')} 수집 완료</p>
                </div>
                
                <div class="summary">
                    <h2>📊 수집 현황</h2>
                    <p>• <strong>총 {len(jobs)}개</strong> 공고 발견</p>
                    <p>• 키워드별 분포: {self._get_keyword_stats(jobs)}</p>
                    <p>• 📎 <strong>전체 데이터는 첨부된 CSV 파일을 확인하세요!</strong></p>
                </div>
                
                <h2>🔥 주요 공고 미리보기 (최대 10개)</h2>
        """

        # 상위 10개 공고만 이메일에 표시
        for job in jobs[:10]:  
            html_body += f"""
            <div class="job-item">
                <div class="job-title">{job['title']}</div>
                <div class="company">🏢 {job['company']}</div>
                <div class="details">
                    📍 {' '.join(job['location']) if isinstance(job['location'], list) else job['location']} | 
                    👔 {job['career']} | 
                    🎓 {job['education']} | 
                    ⏰ {job['deadline']}
                </div>
                <a href="{job['link']}" class="btn" target="_blank">지원하기 →</a>
            </div>
            """
            
        if len(jobs) > 10:
            html_body += f"""
            <div style="text-align: center; padding: 20px; background: #fff3cd; border-radius: 8px; margin: 20px 0;">
                <h3>📋 나머지 {len(jobs)-10}개 공고</h3>
                <p>전체 공고는 <strong>첨부된 CSV 파일</strong>에서 확인하세요!</p>
            </div>
            """
        
        html_body += """
                <div style="text-align: center; margin-top: 30px; padding: 20px; background: #f8f9fa;">
                    <p>🤖 Python 자동화 시스템이 수집했습니다</p>
                    <p style="font-size: 12px; color: #6c757d;">
                        매일 오전 9시에 새로운 공고를 확인해드립니다
                    </p>
                </div>
            </body>
        </html>
        """

        # 이메일 전송
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = email_config['sender_email']
            msg['To'] = email_config['receiver_email']
            msg['Subject'] = subject

            # HTML 내용 첨부
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)

            # CSV 파일 첨부
            csv_filename = self.save_to_csv(jobs)  # CSV 파일 생성
            if csv_filename and os.path.exists(csv_filename):
                with open(csv_filename, 'rb') as attachment:
                    part = MIMEApplication(attachment.read(), _subtype='csv')
                    part.add_header('Content-Disposition', 'attachment', 
                                filename=f"채용공고_{datetime.now().strftime('%Y%m%d')}.csv")
                    msg.attach(part)

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(email_config['sender_email'], email_config['app_password'])
            server.send_message(msg)
            server.quit()

            print("📧 이메일 알림을 성공적으로 보냈습니다!")
            
        except Exception as e:
            print(f"❌ 이메일 전송 실패: {e}")

    def _get_keyword_stats(self, jobs):
        """키워드별 통계 생성"""
        keyword_counts = {}
        for job in jobs:
            keyword = job.get('keyword', '기타')
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        stats = [f"{k}({v}개)" for k, v in keyword_counts.items()]
        return ", ".join(stats)

def run_advanced_crawler(self, email_config=None):
        """여러가지 필터들을 활용한 크롤링"""
        print("🚀 크롤링 시작!")

        # 다양한 검색 조건들
        search_configs = [     # ← 여기! 들여쓰기 맞춤
            {
                'name': '마케팅 신입 (정규직/계약직)',
                'keyword': '마케팅',
                'job_types': ['정규직', '계약직'],
                'remote_work': True,
            }
        ]

        all_jobs = []

        for config in search_configs:
            print(f"\n📋 {config['name']} 검색 중...")
            keyword = config.pop('name')

            keyword = config.pop('keyword', '데이터')  # keyword 추출
            
            jobs = self.search_jobs(keyword=keyword, **config)
            all_jobs.extend(jobs)
            print(f"✅ {len(jobs)}개 공고 수집")

        
        # 중복 제거
        unique_jobs = []
        seen_links = set()

        for job in all_jobs:
            if job['link'] not in seen_links:
                unique_jobs.append(job)
                seen_links.add(job['link'])

        print(f"\n🎉 총 {len(unique_jobs)}개 고유 공고 수집!")

        # CSV 저장
        # filename = self.save_to_csv(unique_jobs)
        
        # 이메일 알림
        if email_config and unique_jobs:
            self.send_email_notification(unique_jobs, email_config)
        
        return unique_jobs

if __name__ == "__main__":
    crawler = SaraminCrawler()

    # # 예시 1: 이곳에 내가 검색하고 싶은 채용 공고 조건 넣기!! (한번에 3가지까지만 가능)
    # jobs = crawler.search_jobs(
    #     keyword="마케팅",
    #     salary_min="3000만원~",           # 3000만원 이상
    #     company_types=["대기업", "중견기업"],   # 대기업, 중견기업만
    #     job_types=["정규직"],              # 정규직만
    #     work_days=["유연근무제"],             # 유연근무제
    #     exclude_keywords=["학교"]           # '학교' 키워드 제외
    # )
    # print(f"검색 결과: {len(jobs)}개")


    # 예시 2: 완전 자동화 크롤링
    print("\n" + "="*60)
    print("🎯 완전 자동화 크롤링")
    print("="*60)

    # 이메일 설정 (선택사항)
    
    email_config = {
        'sender_email': os.environ.get('EMAIL_SENDER'),
        'receiver_email': os.environ.get('EMAIL_RECEIVER'),
        'app_password': os.environ.get('EMAIL_APP_PASSWORD')
    }

    # 자동화 실행
    # all_jobs = crawler.run_advanced_crawler()
    all_jobs = crawler.run_advanced_crawler(email_config)  # 이메일 알림과 함께


    print(f"\n📊 최종 수집 결과:")
    print(f"   - 총 공고 수: {len(all_jobs)}")
    if all_jobs:
        print(f"   - 첫 번째 공고: {all_jobs[0]['title']}")
        print(f"   - CSV 파일로 저장됨")
