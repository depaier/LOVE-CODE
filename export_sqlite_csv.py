import sqlite3
import csv

def export_sqlite_to_csv(db_file='saju_results.db'):
    """SQLite 데이터베이스의 모든 테이블을 CSV로 export"""
    
    # SQLite 연결
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # 테이블 목록 가져오기 (시스템 테이블 제외)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [table[0] for table in cursor.fetchall()]
    
    print(f"📊 SQLite 데이터베이스에서 {len(tables)}개 테이블 발견")
    
    for table_name in tables:
        try:
            # 테이블 데이터 조회
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY id")
            rows = cursor.fetchall()
            
            if not rows:
                print(f"⚠️ {table_name} 테이블에 데이터가 없습니다.")
                continue
            
            # 컬럼 이름 가져오기
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            
            # CSV 파일 생성
            filename = f"{table_name}_export.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # 헤더 작성
                writer.writerow(columns)
                
                # 데이터 작성
                for row in rows:
                    writer.writerow(row)
            
            print(f"✅ {table_name} 테이블 → {filename} ({len(rows)}개 행)")
            
        except Exception as e:
            print(f"❌ {table_name} 테이블 export 실패: {e}")
    
    conn.close()
    print("🎉 SQLite 데이터 CSV export 완료!")

if __name__ == '__main__':
    export_sqlite_to_csv()
