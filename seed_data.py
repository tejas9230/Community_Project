import os
import bcrypt
from datetime import datetime, timedelta
from db import get_db, q, USE_POSTGRES

def seed():
    conn = get_db()
    cur = conn.cursor()

    print(f"Seeding database using backend: {'PostgreSQL (Supabase)' if USE_POSTGRES else 'SQLite'}...")

    # 1. Users Data
    users = [
        ("admin", "admin123", "Admin", None, "admin@scs.gov.in", "+919876543210"),
        ("citizen1", "user123", "Citizen", None, "citizen1@gmail.com", "+919812345678"),
        ("citizen2", "user123", "Citizen", None, "citizen2@gmail.com", "+919823456789"),
        ("citizen3", "user123", "Citizen", None, "citizen3@gmail.com", "+919834567890"),
        ("officer_roads", "roads123", "Officer", "Roads & Infrastructure", "roads.officer@scs.gov.in", "+919845678901"),
        ("officer_drainage", "drain123", "Officer", "Drainage & Sewerage", "drainage.officer@scs.gov.in", "+919856789012"),
        ("officer_sanitation", "clean123", "Officer", "Sanitation & Waste", "sanitation.officer@scs.gov.in", "+919867890123"),
        ("officer_electricity", "power123", "Officer", "Electricity & Lighting", "electricity.officer@scs.gov.in", "+919878901234"),
    ]

    for uname, pw, role, dept, email, phone in users:
        hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        try:
            cur.execute(q("""
                INSERT INTO users (username, password, role, department, email, phone)
                VALUES (?, ?, ?, ?, ?, ?)
            """), (uname, hashed, role, dept, email, phone))
        except Exception as e:
            print(f"Skipped user {uname}: {e}")

    # 2. Sample Complaints Data
    sample_complaints = [
        ("citizen1", "Road Damage", "Severe deep pothole causing traffic slowdown near MVP Colony main intersection.", "Pending", "MVP Colony, Visakhapatnam", "https://images.unsplash.com/photo-1515162816999-a0c47dc192f7", 17.7332, 83.3184, "High", "Roads & Infrastructure", "Under inspection", None, "05-08-2026 10:30", 1, "Verified", 0.0, 14, 1, "officer_roads", "12-08-2026"),
        ("citizen2", "Drainage", "Overflowing sewage drain on 5th avenue. Strong odor and health hazard for residents.", "In Progress", "5th Avenue, Resapuvanipalem, Visakhapatnam", "https://images.unsplash.com/photo-1541888946425-d0fbb186a5b2", 17.7210, 83.3050, "Urgent", "Drainage & Sewerage", "Maintenance team dispatched", None, "04-08-2026 14:15", 0, "Pending", 0.0, 8, 1, "officer_drainage", "08-08-2026"),
        ("citizen3", "Garbage", "Uncollected garbage pile accumulated near the community park gate for over 3 days.", "Resolved", "Community Park Gate, Siripuram, Visakhapatnam", "https://images.unsplash.com/photo-1530587191325-3db32d826c18", 17.7200, 83.3150, "Medium", "Sanitation & Waste", "Sanitation truck cleared the spot.", "https://images.unsplash.com/photo-1530587191325-3db32d826c18", "02-08-2026 09:00", 0, "Verified", 92.5, 21, 0, "officer_sanitation", "06-08-2026"),
        ("citizen1", "Public Property", "Broken street lamp post flickering near Dwarka Nagar bus stop.", "Pending", "Dwarka Nagar 3rd Lane, Visakhapatnam", "https://images.unsplash.com/photo-1509114397022-ed747cca3f65", 17.7280, 83.3010, "Low", "Electricity & Lighting", None, None, "06-08-2026 18:45", 0, "Pending", 0.0, 3, 0, "officer_electricity", "11-08-2026"),
        ("citizen2", "Road Damage", "Multiple asphalt cracks and cave-in after heavy rainfall near National Highway connector.", "In Progress", "NH Connector, Maddilapalem, Visakhapatnam", "https://images.unsplash.com/photo-1515162816999-a0c47dc192f7", 17.7390, 83.3220, "High", "Roads & Infrastructure", "Patch work scheduled", None, "03-08-2026 11:20", 1, "Verified", 0.0, 19, 0, "officer_roads", "10-08-2026"),
        ("citizen3", "Traffic", "Non-functional traffic signal at RTC Complex main junction causing severe jams.", "Pending", "RTC Complex Junction, Visakhapatnam", "https://images.unsplash.com/photo-1508873696983-2df515122519", 17.7250, 83.3030, "High", "Traffic Management", None, None, "06-08-2026 08:10", 0, "Pending", 0.0, 11, 0, None, "09-08-2026"),
        ("citizen1", "Water Supply", "Low water pressure and dirty tap water supply reported in Sector 4 residents block.", "In Progress", "Sector 4, Lawsons Bay Colony, Visakhapatnam", "https://images.unsplash.com/photo-1541888946425-d0fbb186a5b2", 17.7300, 83.3340, "Medium", "Water Supply Department", "Pipeline pressure test in progress", None, "05-08-2026 16:30", 0, "Pending", 0.0, 6, 0, None, "09-08-2026")
    ]

    for uname, cat, desc, status, addr, img, lat, lon, prio, dept, remark, res_img, created, needs_v, v_status, res_score, upv, is_emerg, assign, sla in sample_complaints:
        try:
            cur.execute(q("""
                INSERT INTO complaints (
                    username, category, description, status, address, image_path,
                    latitude, longitude, priority, department, officer_remark,
                    resolution_image, created_at, needs_verification, verification_status,
                    resolution_score, upvotes, is_emergency, assigned_to, sla_deadline
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """), (uname, cat, desc, status, addr, img, lat, lon, prio, dept, remark, res_img, created, needs_v, v_status, res_score, upv, is_emerg, assign, sla))
        except Exception as e:
            print(f"Error inserting sample complaint: {e}")

    # 3. Announcements
    announcements = [
        ("Monsoon Road Repair & Maintenance Drive 2026", "Municipal corporation teams are inspecting and patching all major potholes across MVP & Maddilapalem sectors. Please report new hazards on SCS portal.", "admin", "05-08-2026 10:00", "20-08-2026", 1),
        ("Water Supply Pipeline Maintenance Schedule", "Scheduled maintenance on main water line from 10:00 AM to 04:00 PM tomorrow in Siripuram district.", "admin", "06-08-2026 09:00", "10-08-2026", 1)
    ]

    for title, body, cby, cat, exp, act in announcements:
        try:
            cur.execute(q("""
                INSERT INTO announcements (title, body, created_by, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """), (title, body, cby, cat, exp, act))
        except Exception as e:
            print(f"Announcement error: {e}")

    conn.commit()
    conn.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed()
