Development Workflow

Review the request, think about it, and brainstorm
Use /superpowers:brainstorming for new features
Use /superpowers:systematic-debugging for bug fixes
Ask clarifying questions
Think hard and make a plan
Only when we agree on a plan, create a detailed to-do list using the todo write function, with checkpoints for each phase
If writing code, add these review tasks at the end of the to-do list:
A. Run the `pattern-reviewer` sub-agent
B. Run the `code-simplifier:code-simplifier` plugin
C. Run the `security-code-reviewer` sub-agent
D. For frontend changes:
      I. Run the `ui-design-reviewer` sub-agent to verify visually
      II. Run these impeccable reviews:
      `/impeccable:critique` — UX and design quality review
      `/impeccable:audit` — technical quality (accessibility, performance, anti-patterns)
Once we agree on the to-do list, start implementation
During implementation:
A. Keep things simple and stick to the requested scope
B. Do NOT over-complicate things
C. Do NOT add unnecessary complexity
D. For frontend changes:
      I. Use `agent-browser` to verify visually. The app runs locally via `lcli` (URL in project README).
      II. Use impeccable skills when relevant:
         `/impeccable:polish` — final refinement pass before marking frontend work done
         `/impeccable:clarify` — improve user-facing copy, labels, error messages
         `/impeccable:arrange` — fix layout, spacing, or visual hierarchy issues
         `/impeccable:adapt` — verify responsive behavior across screen sizes
At the end of implementation, use /superpowers:verification-before-completion
