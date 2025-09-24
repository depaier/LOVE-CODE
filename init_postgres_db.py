import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# 환경변수 로딩
load_dotenv()

def get_postgres_connection():
    """PostgreSQL 데이터베이스 연결을 반환"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL 환경변수가 설정되지 않았습니다.")

    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def init_postgres_db():
    """PostgreSQL 데이터베이스 초기화"""
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()

        # results 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                mbti TEXT NOT NULL,
                instagram_id TEXT NOT NULL,
                saju_result TEXT NOT NULL,
                ai_analysis TEXT NOT NULL,
                is_matched BOOLEAN DEFAULT FALSE,
                gender TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # matches 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id SERIAL PRIMARY KEY,
                user1_id INTEGER NOT NULL,
                user2_id INTEGER NOT NULL,
                compatibility_score INTEGER NOT NULL,
                matching_reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user1_id) REFERENCES results(id) ON DELETE CASCADE,
                FOREIGN KEY (user2_id) REFERENCES results(id) ON DELETE CASCADE,
                UNIQUE(user1_id, user2_id)
            )
        ''')

        # student_id에 인덱스 생성 (중복 체크용)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_results_student_id ON results(student_id)
        ''')

        # is_matched에 인덱스 생성 (매칭 조회용)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_results_is_matched ON results(is_matched)
        ''')

        # matches 테이블에 인덱스 생성
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_matches_user1_id ON matches(user1_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_matches_user2_id ON matches(user2_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(compatibility_score DESC)
        ''')

        conn.commit()
        cursor.close()
        conn.close()

        print("✅ PostgreSQL 데이터베이스가 성공적으로 초기화되었습니다.")

    except Exception as e:
        print(f"❌ PostgreSQL 데이터베이스 초기화 실패: {e}")
        raise

if __name__ == '__main__':
    init_postgres_db()
