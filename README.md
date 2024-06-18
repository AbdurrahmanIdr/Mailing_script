# Email Notification System with Flask

## Project Overview

This Flask application offers a comprehensive and user-friendly solution for managing email notifications. It employs the efficient delivery of customized messages with attached PDFs to targeted user groups or individuals.:

- **Send customized email notifications:** Craft tailored messages with attached PDFs to specific user groups or individuals.
- **Streamlined user management:** Effortlessly add, remove, and manage user data for efficient notification distribution.
- **Secure admin controls:** Maintain administrative privileges with features like creating, removing, and managing admin accounts.
- **Reliable asynchronous operations:** Send notifications efficiently in the background, ensuring smooth application performance.
- **Resilient error handling:** Automatically retry failed email deliveries to guarantee successful communication.
- **Comprehensive progress tracking:** Monitor the status of email sending tasks in real-time for informed decision-making.
- **Consolidated log export:** Generate ZIP archives of logs and errors for detailed analysis and troubleshooting.
- **Secure File Uploads:** Upload various file types (including PDFs) for attachment to email notifications.
- **Flexible File/Folder Deletion:** Remove uploaded files that are no longer required, streamlining storage management.

## Features

- **User Management**
  - Add new users to the system.
  - Remove existing users from your notification lists.
  - View and manage all user data within a centralized interface.
- **Admin Management**
  - Create new administrator accounts to delegate tasks and manage access.
  - Remove administrator accounts, upholding security best practices.
  - Manage existing admin accounts, including password changes for enhanced security.
- **Email Sending**
  - Craft dynamic email notifications with attachments for targeted communication.
  - Send emails asynchronously to avoid blocking user interaction with the application.
- **Error Handling and Retries**
  - Automatically attempt to resend emails that encounter failures, ensuring high delivery rates.
- **Tracking and Reporting**
  - Monitor the progress of email sending tasks in real-time for clear visibility.
  - Export detailed logs and error messages as ZIP archives for comprehensive analysis and auditing.

## Installation

**Prerequisites:**

- Python
- Flask

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/AbdurrahmanIdr/Mailing_script.git
   cd Mailing_script
   ```

2. **Create and Activate a Virtual Environment (Recommended):**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up the Database:**

   **Option 1: Using `init_db.py` (if available):**

      ```bash
      python init_db.py
      ```

   **Option 2: Using Flask commands (if `init_db.py` is not provided):**

      ```bash
      flask db init
      flask db migrate
      flask db upgrade
      ```

5. **Configure Email Settings:**

   - Update the `config.ini` file with your email server details:

     ```ini
     [Email]
     smtp_server = smtp.google.com
     smtp_port = 465
     sender_email = your_email@example.com
     sender_password = your_email_password  # **Use an App Password, not your regular password**
     ```

   - **Creating an App Password:**

     1. Visit your Google Account Security Settings ([https://myaccount.google.com/intro/security](https://myaccount.google.com/intro/security)).
     2. Under "Signing in to Google," select 2-Step Verification (if enabled).
     3. At the bottom, select App passwords.
     4. Choose "Select app" and pick "Other (Custom name)".
     5. Enter a descriptive name (e.g., "Email Notification System").
     6. Click "Generate" and copy the 16-character App Password.
     7. Paste this App Password into the `sender_password` field in `config.ini`.

     **If App Passwords are not available:**

     - Visit [https://myaccount.google.com/security](https://myaccount.google.com/security) and then [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) to set up an App Password.

6. **Run the Application:**

   ```bash
   flask run
   ```

## Usage

**User Management:**

- **Add User:** Navigate to `/add_user/` to create a new user.
- **Remove User:** Navigate to `/remove_user/` to delete an existing user.
- **Manage Users:** Navigate to `/manage_users/` to view and modify user information.

**Admin Management:**

- **Add Admin:** Navigate to `/add_admin/` to create a new administrator account.
- **Remove Admin:** Navigate to `/remove_admin/` to delete an existing admin account (excluding currently logged-in admin for security).
- **Manage Admins:** Navigate to `/manage_admins/` to view and manage all admin accounts, including password changes.

**Email Operations:**

- **Send Emails:** Navigate to the appropriate form to initiate email sending. You can track the progress (`/progress_mail/<task_id>/`).
- **Retry Failed Emails:** Navigate to `/retry_page/` to attempt sending emails that previously failed.
- **Export Logs:** Navigate to `/export_logs/` to download a ZIP archive containing logs and errors for troubleshooting.

**Cancel Tasks:**

- **Cancel Task:** Navigate to `/cancel_task/` to terminate an ongoing email sending task.

**Change Password:**

- **Change Password:**  Navigate to `/change_pswd/` to modify your admin password for enhanced security.

## Project Structure

```
├── app.py          # Main Flask application file with routes and functionalities
├── config.ini      # Configuration file for email settings and database connection
├── data/           # Optional directory for storing user data or logs (if applicable)
├── db.sqlite        # SQLite database file (if using SQLAlchemy)
├── init_db.py*      # Optional script for database initialization (if using SQLAlchemy)
├── LICENCE          # Project license file
├── migrations/      # Directory for database migrations (if using SQLAlchemy)
├── models/          # Directory containing database models for users, admins, emails, etc.
│   ├── __init__.py   # Empty file to mark the directory as a Python package
│   ├── explorer.py*  # Optional file for database exploration or manipulation
│   ├── mail_mod.py    # File defining email sending functionality
│   └── pdf_rel.py*    # Optional file for handling PDF attachments (if applicable)
├── README.md        # This file (project documentation)
├── requirements.txt # File listing required dependencies for the project
├── static/          # Directory for static assets like CSS, JavaScript, or images
│   ├── css/        # Subdirectory for CSS stylesheets
│   ├── icons/       # Subdirectory for application icons
│   ├── images/      # Subdirectory for application images
│   └── scripts/     # Subdirectory for JavaScript scripts
└── templates/      # Directory containing HTML templates for different web pages
    ├── add_admin.html # Template for adding a new administrator
    ├── add_user.html  # Template for adding a new user
    ├── admin_control.html  # Template for the admin control panel
    ├── base.html      # Base template for other HTML pages
    ├── directories.html*  # Optional template for managing user categories (if applicable)
    ├── login.html     # Template for user login
    ├── login_base.html   # Base template for login and registration pages
    ├── manage_admins.html # Template for managing administrator accounts
    ├── manage_users.html  # Template for managing user accounts
    ├── progress.html     # Template for displaying email sending progress
    ├── query_db.html*    # Optional template for querying the database (if applicable)
    ├── results.html      # Template for displaying query results
    ├── results_visual.html*  # Optional template for visualizing query results (if applicable)
    ├── retry_page.html   # Template for retrying failed email deliveries
    ├── split_enc.html*    # Optional template for handling split or encrypted data (if applicable)
    ├── view_file.html*    # Optional template for viewing attached files (if applicable)
    └── view_users.html  # Template for viewing a list of users
```

## Contributions

We welcome contributions to this project! Please submit a pull request or open an issue to discuss any changes or enhancements.

## License

This project is licensed under the terms of the [ALMEIDA License](LICENCE).

## Contact

For questions or support, please contact the project maintainers at

- [ARAF M](mailto:mz.araf@gmail.com)
- [Abdurrahman Idris](mailto:abdurrahmaneedrees@gmail.com).

**Additional Notes:**

- Files marked with an asterisk (*) are optional and may not be present in every project.
- The project structure may vary slightly depending on the specific libraries and frameworks used.
