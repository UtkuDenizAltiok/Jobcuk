# Troubleshooting

Find the message or situation you see, then follow the steps.

## Starting Jobcu

**Mac: "Apple could not verify 'Start Jobcu.command' is free of malware"**
Click **Done**, then open **System Settings** → **Privacy & Security**, scroll down, and click
**Open Anyway** next to "Start Jobcu.command". See
[Install and start](install-and-start.md#3a-start-jobcu-on-a-mac).

**Mac: "could not be executed because you do not have appropriate access privileges"**
The file lost its "can be started" setting while unpacking. Delete the folder, download the ZIP
again, and unpack it by double-clicking (don't use other unpacking apps).

**Windows: "Windows protected your PC"**
Click **More info**, then **Run anyway**.

**"The helper couldn't be installed"**
Check your internet connection and double-click **Start Jobcu** again. Company or school
computers sometimes block installing programs; try a personal computer.

**The window says "Jobcu stopped because of a problem" or closes right away**
Double-click **Start Jobcu** again. If it happens again, take a screenshot of the window and send it
to Utku.

**"An older version of Jobcu is still running. Replacing it…"**
That's normal after an update. Wait a few seconds.

**"Jobcu couldn't close the older version by itself"**
Close any other Jobcu window (Mac: the Terminal window, Windows: the black window), then
double-click **Start Jobcu** again. If you can't find it, restart your computer.

**The browser didn't open**
Open your browser yourself and go to the address shown in Jobcu's window, usually
`http://127.0.0.1:8765`.

**The page says "Jobcu's engine isn't answering"**
Jobcu's window was closed. Double-click **Start Jobcu** again.

## Settings and keys

**"The AI provider didn't accept the key"**
Copy the whole key again (no spaces at the start or end), click **Replace**, paste, **Save**, and
test again. Check that you picked the provider the key belongs to.

**"The AI provider doesn't know this model name"**
Click **Load model list** and pick a model from the list.

**"Your AI allowance is used up for now"**
A free allowance usually resets daily; try again tomorrow, or check your account on the provider's
website.

**"The key works, but the AI provider says you've hit a short-term limit"**
Wait a minute and test again.

**"Adzuna didn't accept these keys"**
Check that the Application ID (short) and the Application Key (long) are in the right boxes.

## Searching

**The search is slow**
2–5 minutes is normal. Jobcu reads job sites politely and waits when an AI allowance asks it to.
Searching everywhere (empty location box) takes longer.

**"AI limit reached, continuing more slowly"**
Normal on a free AI allowance. Jobcu waits and continues by itself.

**"… today's free requests are used up" (e.g. Adzuna)**
That site's free daily limit is reached. Searches still use the other sites; the limit resets
the next day.

**"Please upload your CV first"**
Add your CV and cover letter under **Your documents** on the Search page.

**No jobs or very few jobs**
Try **Posted within: 1 week**, a wider location (a country instead of a city), or tick more job
types. Some countries have fewer sources in this test version (see the README).

**A job seems scored wrongly**
That's valuable feedback. Tell Utku which job, its score, and what you'd expect.

## Anything else

Take a screenshot (make sure no keys or personal details are visible) and send it to Utku with a
short description of what you did.
