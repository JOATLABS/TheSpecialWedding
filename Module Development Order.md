# Module Development Order

#### **1\. Base Project Setup & Core Infrastructure**

* **Set up project structure:** Docker Compose, FastAPI project, MongoDB config, `.env` handling.

  project-root/

  ├── app/

  │   ├── main.py

  │   ├── api/

  │   │   └── health.py

  │   └── core/

  │       └── config.py

  ├── requirements.txt

  ├── Dockerfile

  └── docker-compose.yml

* **Test:** Ensure containers spin up, health check endpoint (`GET /health`) returns 200\.

---

#### **2\. Guest Access & Invite Token Flow**

* **Endpoints:**  
  * `GET /invite/{token}`  
* **Features:**  
  * Guest model with token validation.  
  * Simple JSON response to confirm token status.  
* **Test:** Manually call endpoint with test token and verify guest identity retrieval.

---

#### **3\. RSVP Submission**

* **Endpoints:**  
  * `POST /rsvp`  
* **Features:**  
  * Save RSVP data linked to token.  
  * Pydantic validation.  
  * Prevent duplicate submission.  
* **Test:** Submit RSVP using Postman or curl, verify data in Mongo.

---

#### **4\. Admin API: RSVP Viewer**

* **Endpoints:**  
  * `GET /admin/rsvps`  
* **Features:**  
  * JWT/token protection.  
  * Return RSVP list as JSON.  
* **Test:** Query via token, export as CSV via script or admin GUI.  
---

#### **5\. Python GUI: RSVP Table**

* **GUI Features:**  
  * Input: API URL \+ token  
  * Button: Fetch RSVPs  
  * Table View \+ CSV export

* **Test:** Use GUI to query API and confirm RSVP visibility.

---

#### **6\. Gallery (Pre-Wedding Images Only)**

* **Endpoints:**  
  * `POST /admin/gallery/upload`  
  * `GET /gallery`  
* **Features:**  
  * Developer uploads via GUI to S3 bucket.  
  * Public-facing gallery loads images with metadata.  
* **Test:** Upload images using script or GUI; view from public endpoint.

---

#### **7\. Reminder System (SMS via Twilio)**

* **Endpoints:**  
  * `POST /admin/reminders/send`  
* **Features:**  
  * Send SMS to guests who opted in.  
  * Track which reminder round has been sent.  
* **Test:** Use GUI to trigger reminders and confirm via SMS.

---

#### **8\. Event Map, Registry, Wedding Details (Static Content)**

* **Static Frontend Pages:**  
  * Interactive Google Map  
  * Registry links (embedded or external)  
  * Timeline, attire info, etc.  
* **Test:** Navigate site, check correctness of links/maps.

---

#### **9\. Final Polish: Tokenized Guest Links**

* Create a script to generate tokenized URLs  
* Send them manually or integrate with reminder system  
* **Test:** Open guest link and validate unique access

---

### **🧪 Testing Strategy**

* Use **Postman** for REST API tests in early modules

* Develop a **mock MongoDB loader** for inserting test data

* CLI and GUI tools for manual testing before frontend connects

* Later, integrate **Pytest** with FastAPI’s test client for automation

