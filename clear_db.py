from replit import db

def clear_all_data():
    print("Finding all keys...")
    keys = db.keys()
    count = 0
    for key in keys:
        if key.startswith("user:") or key.startswith("convos:"):
            del db[key]
            count += 1
    print(f"Cleared {count} items (users and conversations).")

if __name__ == "__main__":
    confirm = input("Are you sure you want to delete ALL user accounts and history? (y/n): ")
    if confirm.lower() == 'y':
        clear_all_data()
    else:
        print("Operation cancelled.")
