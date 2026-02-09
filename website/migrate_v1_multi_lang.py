import os
import asyncio
import asyncpg

async def run_migration():
    database_url = os.getenv("DATABASE_URL", "postgresql://mars_user:mars_password@db:5432/mars_blog")
    print(f"Connecting to database...")
    
    # Retry logic if db is not ready
    retries = 5
    conn = None
    while retries > 0:
        try:
            conn = await asyncpg.connect(database_url)
            break
        except Exception as e:
            print(f"Waiting for database... ({retries} retries left)")
            await asyncio.sleep(2)
            retries -= 1
    
    if not conn:
        print("Could not connect to database.")
        return

    try:
        print("Applying migration: adding title_it and content_it columns...")
        
        async with conn.transaction():
            columns = await conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'posts' 
                AND column_name IN ('title_it', 'content_it')
            """)
            existing_cols = [c['column_name'] for c in columns]
            
            if 'title_it' not in existing_cols:
                print("Adding column 'title_it'...")
                await conn.execute("ALTER TABLE posts ADD COLUMN title_it TEXT;")
            
            if 'content_it' not in existing_cols:
                print("Adding column 'content_it'...")
                await conn.execute("ALTER TABLE posts ADD COLUMN content_it TEXT;")
                
            print("Migration completed successfully.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migration())
