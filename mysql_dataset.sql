BEGIN TRANSACTION;
CREATE TABLE announcements(
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        body        TEXT NOT NULL,
        created_by  TEXT DEFAULT 'admin',
        created_at  TEXT,
        expires_at  TEXT,
        is_active   INTEGER DEFAULT 1
    );
INSERT INTO "announcements" VALUES(1,'Monsoon Road Repair & Maintenance Drive 2026','Municipal corporation teams are inspecting and patching all major potholes across MVP & Maddilapalem sectors. Please report new hazards on SCS portal.','admin','05-08-2026 10:00','20-08-2026',1);
INSERT INTO "announcements" VALUES(2,'Water Supply Pipeline Maintenance Schedule','Scheduled maintenance on main water line from 10:00 AM to 04:00 PM tomorrow in Siripuram district.','admin','06-08-2026 09:00','10-08-2026',1);
CREATE TABLE community_settings(
        id INTEGER PRIMARY KEY,
        community_name TEXT,
        latitude REAL,
        longitude REAL,
        radius REAL
    );
INSERT INTO "community_settings" VALUES(1,'MVGR',18.062229,83.403873,10.0);
CREATE TABLE complaint_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL,
    officer_username TEXT,
    old_status TEXT,
    new_status TEXT,
    remarks TEXT,
    action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id)
);
INSERT INTO "complaint_history" VALUES(1,3,'roads','Pending','Resolved','hello','2026-07-09 16:54:00');
INSERT INTO "complaint_history" VALUES(2,4,'roads','Pending','Resolved','None','2026-07-12 14:48:45');
INSERT INTO "complaint_history" VALUES(3,14,'roads','Pending','Resolved','None','2026-07-13 16:18:07');
INSERT INTO "complaint_history" VALUES(4,15,'roads','Pending','Resolved','None','2026-07-13 16:25:59');
INSERT INTO "complaint_history" VALUES(5,7,'roads','Pending','Resolved','None','2026-07-16 15:39:45');
INSERT INTO "complaint_history" VALUES(6,8,'roads','Pending','Resolved','None','2026-07-16 15:39:52');
INSERT INTO "complaint_history" VALUES(7,17,'roads','Pending','Resolved','None','2026-07-16 15:39:57');
INSERT INTO "complaint_history" VALUES(8,18,'roads','Pending','Resolved','None','2026-07-16 15:40:03');
INSERT INTO "complaint_history" VALUES(9,11,'roads','Pending','Resolved','None','2026-07-16 15:40:08');
INSERT INTO "complaint_history" VALUES(10,16,'roads','Pending','Resolved','None','2026-07-16 15:40:12');
INSERT INTO "complaint_history" VALUES(11,16,'roads','Resolved','Resolved','None','2026-07-16 15:40:12');
INSERT INTO "complaint_history" VALUES(12,1,'roads','Pending','Resolved','None','2026-07-16 15:40:17');
INSERT INTO "complaint_history" VALUES(13,22,'roads','Pending','In Progress','None','2026-07-20 16:10:04');
INSERT INTO "complaint_history" VALUES(14,22,'roads','In Progress','In Progress','None','2026-07-20 16:10:32');
INSERT INTO "complaint_history" VALUES(15,22,'roads','Resolved','Resolved','None','2026-07-20 16:24:29');
CREATE TABLE complaint_timeline(
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER,
        actor       TEXT,
        action      TEXT,
        note        TEXT,
        timestamp   TEXT
    );
CREATE TABLE complaint_votes(
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER,
        username     TEXT,
        UNIQUE(complaint_id, username)
    );
CREATE TABLE complaints(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT,
      category TEXT,
      description TEXT,
      status TEXT,
      address TEXT,
      image_path TEXT,
      latitude REAL,
      longitude REAL,
      priority TEXT,

      department TEXT,

      officer_remark TEXT,

      resolution_image TEXT,

      created_at TEXT
    , feedback TEXT, rejection_reason TEXT, rating INTEGER, resolution_score REAL DEFAULT 0, verification_status TEXT DEFAULT 'Pending', needs_verification INTEGER DEFAULT 0, updated_at     TEXT, sla_deadline   TEXT, escalated      INTEGER DEFAULT 0, assigned_to    TEXT, is_emergency        INTEGER DEFAULT 0, upvotes             INTEGER DEFAULT 0);
INSERT INTO "complaints" VALUES(1,'roads','Road Damage','
        bv','Resolved','KRM Colony, Pithapuram Colony, Maddilapalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',17.739262,83.3233605,'Medium','Roads & Infrastructure','None',NULL,NULL,NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(2,'roads','Garbage','
        aff','Pending','KRM Colony, Pithapuram Colony, Maddilapalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',17.739262,83.3233605,'Medium','Sanitation & Waste Management',NULL,NULL,NULL,NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(3,'roads','Road Damage','
        etu','Resolved','KRM Colony, Pithapuram Colony, Maddilapalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',17.739262,83.3233605,'Medium','Roads & Infrastructure','hello','Screenshot_2026-04-18_003827.png',NULL,NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(4,'uma','Road Damage','
    huge pothole near  school','Resolved','Bhanu Nagar, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.77416367227896572e+01,8.332481559320140719e+01,'High','Roads & Infrastructure','None',NULL,'10-07-2026 20:57',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(5,'uma','Street Light','
    Street light near bus stop is not working','Pending','Bhanu Nagar, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774162323922701035e+01,8.332482077876498749e+01,'High','Electricity & Street Lighting',NULL,NULL,'10-07-2026 22:54',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,1,NULL,0,0);
INSERT INTO "complaints" VALUES(6,'uma','Street Light','
    Lamp post beside the bus stand has stopped working','Pending','Bhanu Nagar, Pithapuram Colony, Maddilapalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',17.741598,83.324867,'High','Electricity & Street Lighting',NULL,NULL,'10-07-2026 22:55',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,1,NULL,0,0);
INSERT INTO "complaints" VALUES(7,'uma','Road Damage','
            Huge pothole near Government School causing accidents.','Resolved','Bhanu Nagar, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',17.741615,83.324814,'High','Roads & Infrastructure','None',NULL,'12-07-2026 14:25',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(8,'tarun','Road Damage','
            Large pothole near Government School is dangerous for vehicles.','Resolved','Bhanu Nagar, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774158668374358783e+01,8.332483784105907887e+01,'High','Roads & Infrastructure','None',NULL,'12-07-2026 14:26',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(9,'uma','Street Light','
            Street light near bus stop is not working.','Pending','Sector 2, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774205595630266786e+01,8.332535563189853179e+01,'High','Electricity & Street Lighting',NULL,NULL,'12-07-2026 14:26',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,1,NULL,0,0);
INSERT INTO "complaints" VALUES(10,'tarun','Street Light','
            Lamp post beside the bus stand has stopped working.','Pending','Kushi Restaurant & Bar, Anakapalli - Visakhapatnam - Anandapuram Main Road, Sector 2, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774193435540139419e+01,8.332748032976198261e+01,'High','Electricity & Street Lighting',NULL,NULL,'12-07-2026 14:27',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,1,NULL,0,0);
INSERT INTO "complaints" VALUES(11,'uma','Road Damage','
            huge pothole near school','Resolved','Sector 2, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.77415587125324059e+01,8.332521991947955087e+01,'High','Roads & Infrastructure','None',NULL,'12-07-2026 20:05',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(12,'uma','Water Supply','
     water  leakage and road damage near school','Pending','Bhanu Nagar, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774160542834344056e+01,8.332484384104691344e+01,'Critical','Water Supply',NULL,NULL,'12-07-2026 20:21',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,1,NULL,0,0);
INSERT INTO "complaints" VALUES(13,'uma','Water Supply','
            road damage and water leakage','Pending','Bhanu Nagar, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774161898200799569e+01,83.3248162174589,'Critical','Water Supply',NULL,NULL,'12-07-2026 20:23',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,1,NULL,0,0);
INSERT INTO "complaints" VALUES(14,'tarun','Road Damage','huge pothole near school  
            ','Resolved','Bhanu Nagar, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.77423909060508862e+01,8.332431230816635548e+01,'Critical','Roads & Infrastructure','None',NULL,'13-07-2026 21:47','hii',NULL,5,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(15,'tarun','Road Damage','
            huge pothole near  school','Resolved','Sector 2, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',17.7415896977338,8.332504047366741417e+01,'High','Roads & Infrastructure','None',NULL,'13-07-2026 21:47','hello',NULL,5,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(16,'tarun','Road Damage','
            huge pothole near school','Resolved','Sector 2, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774161962357807099e+01,8.332492295880935274e+01,'High','Roads & Infrastructure','None',NULL,'13-07-2026 21:55',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(17,'uma','Road Damage','
           

Huge pothole near Government School.','Resolved','Sector 2, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774165726236833862e+01,83.3250534235557,'Critical','Roads & Infrastructure','None',NULL,'16-07-2026 20:37',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(18,'uma','Road Damage','
     

Large pothole near Government School.','Resolved','Bhanu Nagar, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774190042014642187e+01,83.3242056802768,'Critical','Roads & Infrastructure','None',NULL,'16-07-2026 20:37',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(19,'uma','Road Damage','
            huge  pothole near our street','Pending','Lawrence & Mayo, MVP Double Road, Sector 2, Pithapuram Colony, MVP Colony, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774165404303620264e+01,8.333189546222337185e+01,'Critical','Roads & Infrastructure',NULL,NULL,'18-07-2026 20:55',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,1,NULL,0,0);
INSERT INTO "complaints" VALUES(20,'uma','Road Damage','
   huge pothole near our street','Pending','Resavani Palem, Andhra University North Campus, Maddilapalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.77337660730166391e+01,83.3157316593356,'Critical','Roads & Infrastructure',NULL,NULL,'18-07-2026 20:56',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,1,NULL,0,0);
INSERT INTO "complaints" VALUES(21,'uma','Road Damage','
     huge  pothole       ','Pending','Sector 4, Pithapuram Colony, MVP Colony, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','',1.774120435032342158e+01,8.332893434083588601e+01,'High','Roads & Infrastructure',NULL,NULL,'20-07-2026 20:52',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(22,'uma','Road Damage','
            huge pothole','Resolved','Sector 2, Pithapuram Colony, Venkojipalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','images.jpg',1.774242169061022168e+01,83.3270910271301,'Critical','Roads & Infrastructure','None','images_1.jpg','20-07-2026 21:37',NULL,'',NULL,100.0,'Verified',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(23,'uma','Road Damage','
            huge  pothole','Pending','Resavani Palem, Andhra University North Campus, Maddilapalem, Visakhapatnam, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530001, India','images.jpg',1.773373068753570437e+01,8.331569488773367027e+01,'High','Roads & Infrastructure',NULL,NULL,'20-07-2026 21:53',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(24,'uma','Road Damage','huge pothole
            ','Pending','Srinivasa Nagar, Kailasapuram, Visakha Valley Road, Visakhapatnam Urban, Visakhapatnam, Andhra Pradesh, 530008, India','images.jpg',17.7428,83.2735,'High','Roads & Infrastructure',NULL,NULL,'23-07-2026 15:35',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(25,'uma','Road Damage','huge pothole
            ','Pending','Department of Data Engineering, MVGR Girls Hostel Road, Chintalavalasa, Denkada, Vizianagaram, Andhra Pradesh, 535005, India','images.jpg',18.062254,83.403902,'High','Roads & Infrastructure',NULL,NULL,'23-07-2026 15:38',NULL,NULL,NULL,0.0,'Pending',0,NULL,NULL,0,NULL,0,0);
INSERT INTO "complaints" VALUES(26,'citizen1','Road Damage','Severe deep pothole causing traffic slowdown near MVP Colony main intersection.','Pending','MVP Colony, Visakhapatnam','https://images.unsplash.com/photo-1515162816999-a0c47dc192f7',17.7332,83.3184,'High','Roads & Infrastructure','Under inspection',NULL,'05-08-2026 10:30',NULL,NULL,NULL,0.0,'Verified',1,NULL,'12-08-2026',0,'officer_roads',1,14);
INSERT INTO "complaints" VALUES(27,'citizen2','Drainage','Overflowing sewage drain on 5th avenue. Strong odor and health hazard for residents.','In Progress','5th Avenue, Resapuvanipalem, Visakhapatnam','https://images.unsplash.com/photo-1541888946425-d0fbb186a5b2',17.721,83.305,'Urgent','Drainage & Sewerage','Maintenance team dispatched',NULL,'04-08-2026 14:15',NULL,NULL,NULL,0.0,'Pending',0,NULL,'08-08-2026',0,'officer_drainage',1,8);
INSERT INTO "complaints" VALUES(28,'citizen3','Garbage','Uncollected garbage pile accumulated near the community park gate for over 3 days.','Resolved','Community Park Gate, Siripuram, Visakhapatnam','https://images.unsplash.com/photo-1530587191325-3db32d826c18',17.72,83.315,'Medium','Sanitation & Waste','Sanitation truck cleared the spot.','https://images.unsplash.com/photo-1530587191325-3db32d826c18','02-08-2026 09:00',NULL,NULL,NULL,92.5,'Verified',0,NULL,'06-08-2026',0,'officer_sanitation',0,21);
INSERT INTO "complaints" VALUES(29,'citizen1','Public Property','Broken street lamp post flickering near Dwarka Nagar bus stop.','Pending','Dwarka Nagar 3rd Lane, Visakhapatnam','https://images.unsplash.com/photo-1509114397022-ed747cca3f65',17.728,83.301,'Low','Electricity & Lighting',NULL,NULL,'06-08-2026 18:45',NULL,NULL,NULL,0.0,'Pending',0,NULL,'11-08-2026',0,'officer_electricity',0,3);
INSERT INTO "complaints" VALUES(30,'citizen2','Road Damage','Multiple asphalt cracks and cave-in after heavy rainfall near National Highway connector.','In Progress','NH Connector, Maddilapalem, Visakhapatnam','https://images.unsplash.com/photo-1515162816999-a0c47dc192f7',17.739,83.322,'High','Roads & Infrastructure','Patch work scheduled',NULL,'03-08-2026 11:20',NULL,NULL,NULL,0.0,'Verified',1,NULL,'10-08-2026',0,'officer_roads',0,19);
INSERT INTO "complaints" VALUES(31,'citizen3','Traffic','Non-functional traffic signal at RTC Complex main junction causing severe jams.','Pending','RTC Complex Junction, Visakhapatnam','https://images.unsplash.com/photo-1508873696983-2df515122519',17.725,83.303,'High','Traffic Management',NULL,NULL,'06-08-2026 08:10',NULL,NULL,NULL,0.0,'Pending',0,NULL,'09-08-2026',0,NULL,0,11);
INSERT INTO "complaints" VALUES(32,'citizen1','Water Supply','Low water pressure and dirty tap water supply reported in Sector 4 residents block.','In Progress','Sector 4, Lawsons Bay Colony, Visakhapatnam','https://images.unsplash.com/photo-1541888946425-d0fbb186a5b2',17.73,83.334,'Medium','Water Supply Department','Pipeline pressure test in progress',NULL,'05-08-2026 16:30',NULL,NULL,NULL,0.0,'Pending',0,NULL,'09-08-2026',0,NULL,0,6);
CREATE TABLE notifications(

      id INTEGER PRIMARY KEY AUTOINCREMENT,

      username TEXT,

      message TEXT,

      is_read INTEGER DEFAULT 0,

      created_at TEXT

    );
INSERT INTO "notifications" VALUES(1,'roads','📢 Your complaint has been submitted successfully and is awaiting review.',0,'09-07-2026 20:41');
INSERT INTO "notifications" VALUES(2,'roads','📢 Your complaint has been submitted successfully and is awaiting review.',0,'09-07-2026 22:11');
INSERT INTO "notifications" VALUES(3,'roads','📢 Your complaint has been submitted successfully and is awaiting review.',0,'09-07-2026 22:12');
INSERT INTO "notifications" VALUES(4,'roads','📢 Your complaint SCS-0003 has been updated to ''Resolved''.',0,'09-07-2026 22:24');
INSERT INTO "notifications" VALUES(5,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'10-07-2026 20:57');
INSERT INTO "notifications" VALUES(6,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'10-07-2026 22:54');
INSERT INTO "notifications" VALUES(7,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'10-07-2026 22:55');
INSERT INTO "notifications" VALUES(8,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'12-07-2026 14:25');
INSERT INTO "notifications" VALUES(9,'tarun','📢 Your complaint has been submitted successfully and is awaiting review.',0,'12-07-2026 14:26');
INSERT INTO "notifications" VALUES(10,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'12-07-2026 14:26');
INSERT INTO "notifications" VALUES(11,'tarun','📢 Your complaint has been submitted successfully and is awaiting review.',0,'12-07-2026 14:27');
INSERT INTO "notifications" VALUES(12,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'12-07-2026 20:05');
INSERT INTO "notifications" VALUES(13,'uma','📢 Your complaint SCS-0004 has been updated to ''Resolved''.',0,'12-07-2026 20:18');
INSERT INTO "notifications" VALUES(14,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'12-07-2026 20:21');
INSERT INTO "notifications" VALUES(15,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'12-07-2026 20:23');
INSERT INTO "notifications" VALUES(16,'tarun','📢 Your complaint has been submitted successfully and is awaiting review.',0,'13-07-2026 21:47');
INSERT INTO "notifications" VALUES(17,'tarun','📢 Your complaint has been submitted successfully and is awaiting review.',0,'13-07-2026 21:47');
INSERT INTO "notifications" VALUES(18,'tarun','📢 Your complaint SCS-0014 has been updated to ''Resolved''.',0,'13-07-2026 21:48');
INSERT INTO "notifications" VALUES(19,'tarun','📢 Your complaint has been submitted successfully and is awaiting review.',0,'13-07-2026 21:55');
INSERT INTO "notifications" VALUES(20,'tarun','📢 Your complaint SCS-0015 has been updated to ''Resolved''.',0,'13-07-2026 21:55');
INSERT INTO "notifications" VALUES(21,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'16-07-2026 20:37');
INSERT INTO "notifications" VALUES(22,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'16-07-2026 20:37');
INSERT INTO "notifications" VALUES(23,'uma','📢 Your complaint SCS-0007 has been updated to ''Resolved''.',0,'16-07-2026 21:09');
INSERT INTO "notifications" VALUES(24,'tarun','📢 Your complaint SCS-0008 has been updated to ''Resolved''.',0,'16-07-2026 21:09');
INSERT INTO "notifications" VALUES(25,'uma','📢 Your complaint SCS-0017 has been updated to ''Resolved''.',0,'16-07-2026 21:09');
INSERT INTO "notifications" VALUES(26,'uma','📢 Your complaint SCS-0018 has been updated to ''Resolved''.',0,'16-07-2026 21:10');
INSERT INTO "notifications" VALUES(27,'uma','📢 Your complaint SCS-0011 has been updated to ''Resolved''.',0,'16-07-2026 21:10');
INSERT INTO "notifications" VALUES(28,'tarun','📢 Your complaint SCS-0016 has been updated to ''Resolved''.',0,'16-07-2026 21:10');
INSERT INTO "notifications" VALUES(29,'tarun','📢 Your complaint SCS-0016 has been updated to ''Resolved''.',0,'16-07-2026 21:10');
INSERT INTO "notifications" VALUES(30,'roads','📢 Your complaint SCS-0001 has been updated to ''Resolved''.',0,'16-07-2026 21:10');
INSERT INTO "notifications" VALUES(31,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'18-07-2026 20:55');
INSERT INTO "notifications" VALUES(32,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'18-07-2026 20:56');
INSERT INTO "notifications" VALUES(33,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'20-07-2026 20:52');
INSERT INTO "notifications" VALUES(34,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'20-07-2026 21:37');
INSERT INTO "notifications" VALUES(35,'uma','📢 Your complaint SCS-0022 has been updated to ''In Progress''.',0,'20-07-2026 21:40');
INSERT INTO "notifications" VALUES(36,'uma','📢 Your complaint SCS-0022 has been updated to ''In Progress''.',0,'20-07-2026 21:40');
INSERT INTO "notifications" VALUES(37,'uma','🟢 Complaint SCS-0022 has been resolved.',0,'20-07-2026 21:42');
INSERT INTO "notifications" VALUES(38,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'20-07-2026 21:53');
INSERT INTO "notifications" VALUES(39,'uma','🤖 AI verified your complaint SCS-0022: Verified (Score: 100.0%). Status: Resolved.',0,'20-07-2026 21:54');
INSERT INTO "notifications" VALUES(40,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'23-07-2026 15:35');
INSERT INTO "notifications" VALUES(41,'uma','📢 Your complaint has been submitted successfully and is awaiting review.',0,'23-07-2026 15:38');
CREATE TABLE users(
       username TEXT PRIMARY KEY,
       password TEXT,
       role TEXT DEFAULT 'Citizen',
       department TEXT
    , email          TEXT, phone               TEXT);
INSERT INTO "users" VALUES('roads','$2b$12$a9/pfVccB0dvuNSM2iKZguWn.IfUWX3oJ/yIzzoDsGCzK9g3rq6.C','Officer','Roads & Infrastructure',NULL,NULL);
INSERT INTO "users" VALUES('water','$2b$12$L7qE0zPvIbgFT7JolpN4eu5TkE..xrpTB7QDP9Mksc6P.n9IzykIm','Officer','Water Supply',NULL,NULL);
INSERT INTO "users" VALUES('electricity','$2b$12$0jh2P.9MGMCjIPshKdG7.ei6fkFc/kxNr6FLXw0viuGtzRYTBUZxe','Officer','Electricity & Street Lighting',NULL,NULL);
INSERT INTO "users" VALUES('sanitation','$2b$12$/okeiekdvinXSW9WHbh/l.NhYt9QSmInHjrNQC79vYBFU5EjaHDau','Officer','Sanitation & Waste Management',NULL,NULL);
INSERT INTO "users" VALUES('drainage','$2b$12$Wv96gIFMkYkpQiEj9ahijujkpu0goClXXsOcfFfJzGhdqx0ruWfVi','Officer','Drainage & Sewage',NULL,NULL);
INSERT INTO "users" VALUES('parks','$2b$12$Wj8mZdtRrZTHYsoBr0glN.mnSe44akWF6ia7GFavoh8HJtOTO47q6','Officer','Parks & Green Spaces',NULL,NULL);
INSERT INTO "users" VALUES('property','$2b$12$uONeu1Tw6yzk5y3.C.r5DuxiGnLSiEb7hivzykvZNCXtqE.xoJy1O','Officer','Public Property Maintenance',NULL,NULL);
INSERT INTO "users" VALUES('animal','$2b$12$l.Q0t2L0NGheXA9cAUPKfOVMzjBzNasoRqG0dfXWHvjk5JXnI6ODO','Officer','Animal Control',NULL,NULL);
INSERT INTO "users" VALUES('traffic','$2b$12$9hRfml6avHs5TRDGy0epyeLlEXbR6gBNQPdP55T5VSKZd0uy9i0Bi','Officer','Traffic & Public Safety',NULL,NULL);
INSERT INTO "users" VALUES('others','$2b$12$Yw/5ojFofOEPZ0auYJbv8e07faDkCpq1xJ4kIFQpMO/hhVGsXlNoO','Officer','Others',NULL,NULL);
INSERT INTO "users" VALUES('admin','$2b$12$qz5LyOmIg0tn3chK/yeQZO3QaK5o.V11szr8oTLs3.l8ve3toVpEK','Admin',NULL,NULL,NULL);
INSERT INTO "users" VALUES('uma','$2b$12$rGxntiBprA37I14PWkJuUugH2N.1KGBfTjWJzNCOysWgOT9Xk2hfi','Citizen',NULL,NULL,NULL);
INSERT INTO "users" VALUES('tarun','$2b$12$kZFOJIGxuj.Cay06WWcLi.tS2EQf1qzyFmjNc8SjDHppCcWVO3LFe','Citizen',NULL,NULL,NULL);
INSERT INTO "users" VALUES('tarun123','$2b$12$xTCYvA9FQql59fA6TGyaUe5WawE//QPgw.LDZ.xHsJHif3dxqokha','Citizen',NULL,NULL,NULL);
INSERT INTO "users" VALUES('tejas','$2b$12$tzhXnoXPIlGSKsDAVOvra.T/yYzIVqfzCdZyk5NZvkQ.NWSijQlay','Citizen',NULL,NULL,NULL);
INSERT INTO "users" VALUES('citizen1','$2b$12$AGgqavEWuZfypZX08X2Qd.rFrx0BaErwz23uUKcSeu0yK0Gu3gs5m','Citizen',NULL,'citizen1@gmail.com','+919812345678');
INSERT INTO "users" VALUES('citizen2','$2b$12$hoxN49hIdxYl85A046fMz.tJ.lBvpVIcjiRHQOK6azx1QD65Afbty','Citizen',NULL,'citizen2@gmail.com','+919823456789');
INSERT INTO "users" VALUES('citizen3','$2b$12$C7gKOpLFa9OeC4zjiBeL1uZYZNFYlY5GePSpm14t0OVCRD2rwI90i','Citizen',NULL,'citizen3@gmail.com','+919834567890');
INSERT INTO "users" VALUES('officer_roads','$2b$12$k5IrtygvND9/kB9R9bRV6ekht.azFdA09ewmwiD0Ec1cghK0adYZ.','Officer','Roads & Infrastructure','roads.officer@scs.gov.in','+919845678901');
INSERT INTO "users" VALUES('officer_drainage','$2b$12$zqFurcxPg/Jg70h7VK.FTel1gTIAqn2XKKh6MpwPXrj4JaQAphhLC','Officer','Drainage & Sewerage','drainage.officer@scs.gov.in','+919856789012');
INSERT INTO "users" VALUES('officer_sanitation','$2b$12$jTyL7MOfd4cRdmxN6ennMOgZAC2SHvNTD8xVrTOFdWZXKdyUgz5K2','Officer','Sanitation & Waste','sanitation.officer@scs.gov.in','+919867890123');
INSERT INTO "users" VALUES('officer_electricity','$2b$12$BEwbVrHRlvtSvjyMo/e3Y.8Y/QcVZhQLtRM3P6CkYY1egwU0RCpJ.','Officer','Electricity & Lighting','electricity.officer@scs.gov.in','+919878901234');
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('complaints',32);
INSERT INTO "sqlite_sequence" VALUES('notifications',41);
INSERT INTO "sqlite_sequence" VALUES('complaint_history',15);
INSERT INTO "sqlite_sequence" VALUES('announcements',2);
COMMIT;
