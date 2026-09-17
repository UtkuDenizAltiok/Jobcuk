# Install and start Jobcu

This guide takes about 10 minutes. You don't need any technical knowledge: just follow the steps
in order. If something looks different or goes wrong, see
[Troubleshooting](troubleshooting.md).

*Words used here:* **GitHub** is the website where Jobcu is kept. A **ZIP file** is a packed
folder that your computer unpacks with a double-click.

---

## 1. Get access to Jobcu on GitHub

Jobcu is private, so you need a free GitHub account and an invitation.

1. If you don't have a GitHub account yet, go to **github.com**, click **Sign up**, and follow the
   steps. Remember the username you choose.
2. Send your GitHub **username** to Utku, so he can invite you.
3. You'll receive an **email from GitHub** saying you were invited to `UtkuDenizAltiok/jobcu`.
   Click **View invitation**, then **Accept invitation**.

## 2. Download Jobcu

1. Go to **github.com/UtkuDenizAltiok/jobcu** (sign in to GitHub if asked).
2. Click the green **Code** button near the top right of the file list.
3. Click **Download ZIP**. A file called `jobcu-main.zip` is saved, usually in your **Downloads**
   folder.
4. Unpack it:
   - **Mac:** double-click `jobcu-main.zip`. A folder called `jobcu-main` appears.
   - **Windows:** right-click `jobcu-main.zip` → **Extract All…** → **Extract**. A folder called
     `jobcu-main` opens.
5. Move the `jobcu-main` folder somewhere it can stay, for example your **Documents** folder.

---

## 3a. Start Jobcu on a Mac

1. Open the `jobcu-main` folder and double-click **Start Jobcu.command**.
2. **The first time**, your Mac will probably say it can't verify the file ("Apple could not verify
   … is free of malware"), because Jobcu isn't sold through Apple. Click **Done** (not "Move to
   Trash"). Then:
   1. Open the **Apple menu ()** → **System Settings** → **Privacy & Security**.
   2. Scroll down. Next to the message about "Start Jobcu.command", click **Open Anyway**.
   3. Confirm with your Mac password or Touch ID if asked, then click **Open Anyway** again.
3. A window with text opens (this is the **Terminal**, where Jobcu runs). If it asks to install a
   free helper program called **uv**, press **Return**. This happens only once.
4. The **first start takes a few minutes** while Jobcu downloads what it needs. Later starts take
   seconds.
5. If your Mac asks whether Terminal may access a folder (such as Documents or Downloads), click
   **Allow**.
6. Your web browser opens **Jobcu**. 🎉

**Keep the Terminal window open while you use Jobcu.** To stop Jobcu, close that window (if asked,
click **Terminate**).

## 3b. Start Jobcu on Windows

1. Open the `jobcu-main` folder and double-click **Start Jobcu.bat** (it may show as just
   **Start Jobcu**).
2. **The first time**, Windows may show a blue box "Windows protected your PC", because Jobcu isn't
   sold through Microsoft. Click **More info**, then **Run anyway**.
3. A black window opens (this is where Jobcu runs). If it asks to install a free helper program
   called **uv**, press any key. This happens only once. If Windows asks for permission, click
   **Yes**.
4. The **first start takes a few minutes** while Jobcu downloads what it needs. Later starts take
   seconds.
5. If Windows asks whether to allow network access for Python, choose **Private networks** and click
   **Allow**. (Jobcu only talks to your own computer and to the job sites and AI you use.)
6. Your web browser opens **Jobcu**. 🎉

**Keep the black window open while you use Jobcu.** To stop Jobcu, close that window.

---

## Next time

Just double-click **Start Jobcu** again. If the browser page is closed but Jobcu is still running,
double-clicking opens the page again.

## Next step

➡️ **[Get your keys](getting-your-keys.md)**, then **[your first search](first-search.md)**.

---

## Updating Jobcu

When Utku tells you there's a new version:

1. Close Jobcu's window.
2. Download the new ZIP (step 2 above) and unpack it.
3. Delete your old `jobcu-main` folder and put the new one in its place.

**Your data is not in that folder**, so your settings, keys, documents and saved jobs stay safe.

## Removing Jobcu

1. Delete the `jobcu-main` folder.
2. To also delete your Jobcu data (settings, keys, documents, saved jobs), delete this folder:
   - **Mac:** in Finder, click **Go** → **Go to Folder…**, type
     `~/Library/Application Support/Jobcu` and press Return. Delete the `Jobcu` folder.
   - **Windows:** press **Windows + R**, type `%LOCALAPPDATA%` and press Enter. Delete the `Jobcu`
     folder.
