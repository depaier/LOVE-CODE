import sqlite3

# 'saju_results.db'라는 이름의 데이터베이스에 연결합니다.
# 파일이 없으면 자동으로 새로 생성됩니다.
connection = sqlite3.connect('saju_results.db')

# SQL 명령을 실행하기 위한 cursor 객체를 생성합니다.
cursor = connection.cursor()

# 'results'라는 이름의 테이블을 생성합니다.
# IF NOT EXISTS는 테이블이 이미 존재하면 오류 없이 넘어가게 해줍니다.
cursor.execute('''
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        mbti TEXT NOT NULL,
        saju_result TEXT NOT NULL,
        ai_analysis TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# 변경 사항을 데이터베이스에 저장(commit)합니다.
connection.commit()

# 연결을 닫습니다.
connection.close()

print("데이터베이스와 테이블이 성공적으로 생성되었습니다. 'saju_results.db' 파일을 확인하세요.")