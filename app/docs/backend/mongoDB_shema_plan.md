# # MongoDB Shema PlanNormalized for Scalability

| Collection | Key Relationships                                   |
| ---------- | --------------------------------------------------- |
| guests     | Belongs to a wedding, optionally a group_id         |
| rsvps      | References a guest (guest_id)                       |
| plus_ones  | References a guest (guest_id)                       |
| weddings   | Root tenant ID; allows scaling to multiple weddings |

1. Guests Collection: Stores primary invitee details.

```json
{

  "_id":ObjectId,
  "wedding_id":"wedding_001",
  "name":"John Smith",
  "token":"abc123xyz",
  "email":"john@example.com",
  "phone":"1234567890",
  "group_id":"grp_fam_001",      //optional:forfamiliesorsharedinvites
  "plus_one_allowed":true,
  "plus_one_submitted":false,
  "role":"guest",                //guest,admin,vendor,etc.
  "created_at":ISODate,
  "updated_at":ISODate

}
```

2. Rsvps Collection: Tracks each rsvp submission separately; Allows audit trail and updates.

```json
{

  "_id":ObjectId,
  "guest_id":ObjectId,  //referenceto `guests`._id
  "attending":["traditional","reception"],
  "dietary":"No peanuts",
  "submitted_at":ISODate
}
```

3. Plus_ones Collection: Each plus-one is a record tied to a primary guest.

```json
{

  "_id":ObjectId,
  "guest_id":ObjectId,          //whobroughtthisplus-one
  "name":"Jane Doe",
  "dietary":"Vegetarian",
  "attending":["reception"]

}
```

4. weddings Collection: (optional, for multi-wedding reuse)

```json
{

  "_id":"wedding_001",
  "couple_names":"Tolu & Dayo",
  "date":"2025-11-22",
  "slug":"tolu-dayo-wedding",
  "events":[
    {"type":"traditional","date":"2025-11-21"},
    {"type":"white_wedding","date":"2025-11-22"},
    {"type":"reception","date":"2025-11-22"}
  ],
  "created_at":ISODate
}
```
