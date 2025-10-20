# Quiz Competition - Administrator Guide

## Quick Start Guide for Teachers

### First Time Setup

1. **Install the Add-in**
   - Open PowerPoint
   - Go to Insert > Get Add-ins > My Add-ins
   - Click "Upload My Add-in"
   - Select the `manifest.xml` file
   - The add-in appears in the Home tab

2. **Login**
   - Click "Show Task Pane" in the ribbon
   - Enter your credentials
   - Default demo: `teacher@demo.com` / `demo123`

### Creating Your First Quiz

#### Step 1: Create a Quiz
1. Click the **Author** tab
2. Enter a quiz title (e.g., "Math Quiz Week 5")
3. Click **Create New Quiz**
4. You'll see confirmation: "Quiz: Math Quiz Week 5 (ID: 123)"

#### Step 2: Add Questions to Slides
1. Create a new slide in PowerPoint
2. In the add-in, fill in the question form:
   - **Question Title**: "What is 2 + 2?"
   - **Options A-F**: Enter at least 2 options
     - A: "3"
     - B: "4" ← Correct
     - C: "5"
     - D: "6"
   - **Correct Answer**: Select "B"
   - **Timer**: 30 seconds (default)
3. Click **Save to Slide**
4. Repeat for each slide/question

**Tips:**
- Use 2-4 options for quick questions
- Use 5-6 options for more challenging questions
- Set shorter timers (15-20s) for simple recall
- Set longer timers (60-120s) for problem-solving

#### Step 3: Review Your Questions
1. Click **Sync from Slides** to refresh the list
2. You'll see all questions numbered
3. Edit slides if needed and sync again

### Running a Live Quiz Session

#### Before Class

1. **Prepare**
   - Ensure all questions are saved to slides
   - Test your internet connection
   - Have the presentation ready in slideshow mode (optional)

2. **Start Session**
   - Click the **Live** tab
   - Click **Start Quiz**
   - A 6-digit code appears (e.g., "834921")
   - QR code is displayed

3. **Share Join Information**
   - **Option A**: Insert QR code to a slide
     - Click "Insert QR to Slide"
     - Show this slide to students
   - **Option B**: Write code on board
     - Students go to the join URL
     - Enter the 6-digit code

#### During Class

1. **Wait for Students**
   - Watch the participant list fill up
   - You'll see names as students join
   - Participant count updates in real-time

2. **Start First Question**
   - When ready, click **Next Question**
   - Question opens for all students
   - Timer starts automatically

3. **Monitor Responses**
   - **Response Count**: See how many answered
   - **Correct %**: See accuracy in real-time
   - **Leaderboard**: Top 10 students displayed
   - **Stats Bar**: Visual representation of correct answers

4. **Lock Question** (Optional)
   - Click **Lock Question** to prevent late answers
   - Or wait for timer to expire (auto-locks)

5. **Continue Through Questions**
   - Click **Next Question** for each subsequent question
   - Monitor engagement and adjust pacing
   - Students see their running score

6. **End Quiz**
   - After last question, click **End Quiz**
   - Confirm the action
   - Session closes for all students

#### After Class

1. **View Summary**
   - Click **View Summary**
   - See overall statistics:
     - Total participants
     - Per-question accuracy
     - Top performers

2. **Export Results**
   - Click **Export CSV**
   - Opens in Excel/Sheets
   - Contains:
     - Rank
     - Student name
     - Total points
     - Correct answers
     - Total latency
     - Questions answered

3. **Review Performance**
   - Identify difficult questions (low accuracy)
   - Recognize top performers
   - Plan follow-up instruction

### Best Practices

#### Question Design

**DO:**
- ✓ Keep questions clear and concise
- ✓ Use consistent option formatting
- ✓ Test questions before live session
- ✓ Mix difficulty levels
- ✓ Use 3-4 options for most questions

**DON'T:**
- ✗ Use "All of the above" or "None of the above" (confusing in timed format)
- ✗ Make options too long (hard to read on phones)
- ✗ Use trick questions (frustrates students)
- ✗ Have more than 6 options (overwhelming)

#### Session Management

**Pacing:**
- Start with easier questions to build confidence
- Allow 5-10 seconds after timer for students to see results
- Take brief pauses every 5-7 questions
- Total session: 10-15 questions = 15-20 minutes

**Engagement:**
- Announce top 3 after every 5 questions
- Celebrate correct answers
- Use leaderboard to create friendly competition
- Acknowledge participation, not just winners

**Technical:**
- Have backup plan if internet fails
- Test with a few students before full class
- Keep session code visible throughout
- Monitor participant count for disconnections

### Troubleshooting

#### Students Can't Join

**Problem**: "Invalid session code"
- **Solution**: Double-check the code displayed in add-in
- **Solution**: Ensure session is started (not ended)
- **Solution**: Have students refresh the page

**Problem**: QR code doesn't work
- **Solution**: Ensure QR is clearly visible (not blurry)
- **Solution**: Have students enter code manually
- **Solution**: Check join URL is correct

#### Questions Not Appearing

**Problem**: "No questions yet"
- **Solution**: Click "Sync from Slides" in Author tab
- **Solution**: Ensure questions are saved to slides
- **Solution**: Verify quiz is selected

**Problem**: Wrong question opens
- **Solution**: Questions open in order they were created
- **Solution**: Recreate questions in desired order

#### Real-time Issues

**Problem**: Leaderboard not updating
- **Solution**: Check internet connection
- **Solution**: Refresh the add-in
- **Solution**: Restart the session if persistent

**Problem**: Responses not counting
- **Solution**: Ensure question is active (not locked)
- **Solution**: Check students are in correct session
- **Solution**: Verify timer hasn't expired

### Advanced Features

#### Custom Timers
- **Quick Recall**: 15-20 seconds
- **Standard**: 30-45 seconds
- **Problem Solving**: 60-90 seconds
- **Complex**: 90-120 seconds

#### Scoring Strategy
- Current: 1 point per correct answer
- Tiebreaker: Faster correct answers rank higher
- Future: Speed bonuses, partial credit

#### Session Management
- Run multiple sessions from same quiz
- Each session has unique code
- Previous session data is preserved
- Export results from any session

### Tips for Success

1. **Preparation**
   - Create quiz day before
   - Test with colleague
   - Have 2-3 extra questions ready

2. **Engagement**
   - Use quiz as formative assessment
   - Review missed questions immediately
   - Make it fun, not stressful

3. **Follow-up**
   - Share top performers (with permission)
   - Review difficult questions in next class
   - Use data to inform instruction

4. **Technical**
   - Keep add-in open during session
   - Don't close PowerPoint during quiz
   - Save presentation after creating questions

### Common Scenarios

#### Scenario 1: Student Joins Late
- They can join anytime during session
- They'll see current question
- They won't see previous questions
- Their score starts from when they joined

#### Scenario 2: Student Disconnects
- They can rejoin with same name
- Previous answers are saved
- They continue from current question

#### Scenario 3: Need to Pause
- Lock current question
- Don't click "Next Question"
- Students wait in lobby
- Resume by clicking "Next Question"

#### Scenario 4: Wrong Answer Marked Correct
- Cannot change during live session
- Note for manual correction
- Fix question for next session

### Support

**Technical Issues:**
- Check README.md for troubleshooting
- Verify backend server is running
- Check browser console for errors

**Pedagogical Questions:**
- Consult instructional design team
- Review best practices above
- Share experiences with colleagues

### Quick Reference

**Keyboard Shortcuts:**
- None currently (use mouse/touch)

**Session Codes:**
- 6 digits, numeric only
- Valid for single session
- Expires when session ends

**File Locations:**
- Questions: Saved in PowerPoint file
- Results: Export to CSV
- QR Codes: Generated on-demand

**Limits:**
- Questions: Unlimited
- Students: 50+ (tested)
- Options: 2-6 per question
- Timer: 15-120 seconds

---

## Appendix: Sample Quiz

**Title**: "General Knowledge - Week 1"

**Q1**: What is the capital of France?
- A: London
- B: Paris ✓
- C: Berlin
- D: Madrid
- Timer: 30s

**Q2**: Which planet is known as the Red Planet?
- A: Venus
- B: Mars ✓
- C: Jupiter
- D: Saturn
- Timer: 30s

**Q3**: What is 15 × 8?
- A: 110
- B: 120 ✓
- C: 130
- D: 140
- Timer: 20s

**Q4**: Who wrote "Romeo and Juliet"?
- A: Charles Dickens
- B: William Shakespeare ✓
- C: Jane Austen
- D: Mark Twain
- Timer: 30s

**Q5**: What is the largest ocean on Earth?
- A: Atlantic Ocean
- B: Indian Ocean
- C: Pacific Ocean ✓
- D: Arctic Ocean
- Timer: 30s

---

*Last updated: 2025-10-15*
*Version: 1.0.0*
