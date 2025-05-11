**Project Specification Document: Wedding Web Application**

---

### **Overview**

This document outlines the functional and technical requirements for a wedding web application intended to serve up to 500 guests. The goal is to create a reusable and scalable solution that can later be white-labeled or adapted for other weddings.

---

### **Objectives**

1. Deliver a modern, visually engaging, and functional wedding website.  
2. Include core features such as RSVP, interactive event map, a photo gallery, and automated reminders.  
3. Use scalable, modular technology for backend and frontend.  
4. Keep admin interaction lightweight via a Python GUI that interfaces with the API.

---

### **Technology Stack**

* **Frontend:** None (public-facing UI rendered by Next.js; admin via local Python GUI)  
* **UI Framework:** Next.js \+ NextUI  
* **Backend:** FastAPI (Python)  
* **Database:** MongoDB (NoSQL, document-based)  
* **Hosting:** DigitalOcean or Hetzner VM (Dockerized stack)  
* **File Storage:** S3-compatible bucket (e.g., Cloudflare R2 or Wasabi)  
* **SMS Service:** Twilio

---

### **Public Features (Guest-Facing)**

#### **1\. Home Page**

* Parallax scrolling effect using pure CSS.  
* Background features engagement/pre-wedding images.  
* Overlay sections with anchor links to RSVP, Gallery, Registry, FAQ.

#### **2\. RSVP System**

* Guests respond to invitations for:  
  * Traditional (Friday)  
  * White Wedding (Saturday)  
  * Reception (Saturday)  
* RSVP form includes:  
  * Name(s)  
  * Dietary restrictions  
  * Phone number (optional, for text reminders)  
  * Checkbox for consent to receive reminders  
* Generates confirmation and downloadable CSV export.  
* Confirmation page \+ optional calendar file download.

#### **3\. Wedding Registry**

* Link out to external registry platforms or embed iframe.

#### **4\. Gallery (Developer-Managed Only)**

* Developer uploads pre-wedding photos via admin API.  
* Gallery page renders a grid of images pulled from S3-compatible bucket.

#### **5\. Event Map**

* Embed Google Maps for venue location.  
* Provide directions link, parking instructions, and emergency contact.

#### **6\. Wedding Details Page**

* Attire recommendations  
* Timeline of the day(s)  
* Custom notes based on RSVP type (e.g., Traditional vs Reception-only)

#### **7\. FAQ**

* Static list of frequently asked questions, editable via config or admin API.

#### **8\. Acce, ss Control**

* Each guest receives a unique invitation link (`/invite/<token>`) that identifies them.  
* No password or login screen needed.  
* Token is stored in MongoDB and used to identify RSVP submission.

---

### **Admin Interface (Local Python GUI)**

#### **Purpose**

Avoid deploying an online admin portal. Instead, admin functions are accessed via a standalone desktop GUI app that interfaces with backend endpoints.

#### **Functions**

1. **RSVP Viewer**  
   * Fetch RSVP data from FastAPI endpoint.  
   * Display in table with filters and export to CSV.  
2. **Gallery Uploader**  
   * Upload images to storage bucket.  
   * Call FastAPI endpoint to register photo metadata.  
3. **Reminder Sender**  
   * View RSVP list with phone numbers.  
   * Select guests and send SMS reminders via Twilio.  
   * Track sent status per reminder round.  
4. **Photo Moderation (Optional for future)**  
   * Interface to view, approve, or delete guest-uploaded photos (if implemented).

---

### **Backend API Overview (FastAPI)**

#### **Guest Endpoints**

* `POST /rsvp` — Submit RSVP  
* `GET /invite/{token}` — Get guest info for token  
* `GET /gallery` — List gallery images

#### **Admin Endpoints (JWT/Token Protected)**

* `GET /admin/rsvps` — Fetch RSVP submissions  
* `POST /admin/reminders/send` — Trigger SMS reminders  
* `POST /admin/gallery/upload` — Register new image  
* `DELETE /admin/gallery/{id}` — Delete image

---

### **Storage and Deployment**

* **MongoDB Atlas** or self-hosted on the VM  
* **S3 Bucket** for images (Cloudflare R2 preferred for low cost)  
* **FastAPI \+ Uvicorn** hosted with Nginx as reverse proxy  
* **Frontend** built with Next.js and statically served (Vercel optional or deployed via Nginx)  
* **Docker Compose** for service orchestration

---

### **SMS Integration**

* Use Twilio  
* Reminders sent via FastAPI background task or manually via admin GUI  
* Costs controlled by sending only to opted-in numbers

---

### **Security**

* HTTPS enforced  
* JWT authentication for admin routes  
* Mongo input validation via Pydantic models  
* Admin routes are not exposed on the public domain

---

### **Deliverables**

* Working wedding web application with the above features  
* Developer README for deployment and customization  
* Python admin GUI app  
* Sample `.env` file and setup instructions for VM deployment

