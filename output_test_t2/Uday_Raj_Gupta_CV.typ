// Import the rendercv function and all the refactored components
#import "@preview/rendercv:0.3.0": *

// Apply the rendercv template with custom configuration
#show: rendercv.with(
  name: "Uday Raj Gupta",
  title: "Uday Raj Gupta - Resume",
  footer: context { [#emph[Uday Raj Gupta -- #str(here().page())/#str(counter(page).final().first())]] },
  top-note: [ #emph[Last updated in Oct 2026] ],
  locale-catalog-language: "en",
  text-direction: ltr,
  page-size: "a4",
  page-top-margin: 0.18in,
  page-bottom-margin: 0.18in,
  page-left-margin: 0.26in,
  page-right-margin: 0.26in,
  page-show-footer: false,
  page-show-top-note: false,
  colors-body: rgb(0, 0, 0),
  colors-name: rgb(31, 78, 121),
  colors-headline: rgb(31, 78, 121),
  colors-connections: rgb(34, 34, 34),
  colors-section-titles: rgb(31, 78, 121),
  colors-links: rgb(5, 99, 193),
  colors-footer: rgb(128, 128, 128),
  colors-top-note: rgb(128, 128, 128),
  typography-line-spacing: 0.26em,
  typography-alignment: "justified",
  typography-date-and-location-column-alignment: right,
  typography-font-family-body: "Times New Roman",
  typography-font-family-name: "Times New Roman",
  typography-font-family-headline: "Times New Roman",
  typography-font-family-connections: "Times New Roman",
  typography-font-family-section-titles: "Times New Roman",
  typography-font-size-body: 10pt,
  typography-font-size-name: 19pt,
  typography-font-size-headline: 10pt,
  typography-font-size-connections: 10pt,
  typography-font-size-section-titles: 12pt,
  typography-small-caps-name: false,
  typography-small-caps-headline: false,
  typography-small-caps-connections: false,
  typography-small-caps-section-titles: false,
  typography-bold-name: true,
  typography-bold-headline: false,
  typography-bold-connections: false,
  typography-bold-section-titles: true,
  links-underline: false,
  links-show-external-link-icon: false,
  header-alignment: center,
  header-photo-width: 3.5cm,
  header-space-below-name: 0.7cm,
  header-space-below-headline: 0.7cm,
  header-space-below-connections: 0.7cm,
  header-connections-hyperlink: true,
  header-connections-show-icons: false,
  header-connections-display-urls-instead-of-usernames: true,
  header-connections-separator: " | ",
  header-connections-space-between-connections: 0.5cm,
  section-titles-type: "with_full_line",
  section-titles-line-thickness: 0.5pt,
  section-titles-space-above: 6pt,
  section-titles-space-below: 3.5pt,
  sections-allow-page-break: true,
  sections-space-between-text-based-entries: 2.5pt,
  sections-space-between-regular-entries: 4.5pt,
  entries-date-and-location-width: 4.15cm,
  entries-side-space: 0cm,
  entries-space-between-columns: 0.1cm,
  entries-allow-page-break: false,
  entries-short-second-row: false,
  entries-degree-width: 1cm,
  entries-summary-space-left: 0cm,
  entries-summary-space-above: 0pt,
  entries-highlights-bullet:  "○" ,
  entries-highlights-nested-bullet:  [#text(13pt, baseline: -0.6pt)[•]] ,
  entries-highlights-space-left: 15pt,
  entries-highlights-space-above: 1.2pt,
  entries-highlights-space-between-items: 1.5pt,
  entries-highlights-space-between-bullet-and-text: 0.25em,
  date: datetime(
    year: 2026,
    month: 10,
    day: 7,
  ),
)


= Uday Raj Gupta

#connections(
  [#link("mailto:udayrajgupta2003@gmail.com")[udayrajgupta2003\@gmail.com]],
  [GitHub: #link("https://github.com/udayraj2003")[github.com/udayraj2003]],
  [LinkedIn: #link("https://linkedin.com/in/uday-raj-gupta-b7a493262/")[linkedin.com/in/uday-raj-gupta-b7a493262/]],
  [GFG: #link("https://geeksforgeeks.org/profile/udayrajgusc9z")[geeksforgeeks.org/profile/udayrajgusc9z]],
  [LeetCode: #link("https://leetcode.com/u/udayrajgupta2003/")[leetcode.com/u/udayrajgupta2003/]],
  [+917470810014],
  [Pune],
)


== Profile

• Full-stack developer, Software Engineer, and Quality Assurance Engineer with experience in MERN stack, API testing, validation, and defect lifecycle management across SaaS digital platforms. Strong foundation in data structures, system design, scalability, responsive web development, and Agile Scrum workflows.

== Skills

#text(fill: rgb("1f4e79"))[•] #strong[Programming Languages:] C, C++, SQL, OOP, Data Structures, Algorithms

#text(fill: rgb("1f4e79"))[•] #strong[Web Development:] HTML, CSS, JavaScript, React.js, Redux Toolkit, Node.js, Express.js, MongoDB, REST APIs, API Integration, Request Handling, Response Handling, Authentication, CRUD, Responsive Design, Figma, UI/UX

#text(fill: rgb("1f4e79"))[•] #strong[Software Testing:] Functional Testing, Regression Testing, Integration Testing, End-to-End Testing, UAT, API Testing, Test Execution

#text(fill: rgb("1f4e79"))[•] #strong[Tools and Technologies:] GitHub, Version Control, MySQL, Cloudinary, Linux, Jira, Postman, Selenium, Automation Testing

#text(fill: rgb("1f4e79"))[•] #strong[Core Concepts:] Operating Systems, Computer Networks, SDLC, Agile Scrum, System Design, Performance Optimization, Scalability

#text(fill: rgb("1f4e79"))[•] #strong[Soft Skills:] Attention to Detail, Communication, Analytical Thinking, Organizational Skills, Team Collaboration

== Experience

#regular-entry(
  [
    #text(fill: rgb("1f4e79"))[•] #text(fill: rgb("2e75b6"))[#strong[Dice Enterprises]], Pune --- #emph[QA Engineer and Automation Developer]

  ],
  [
    #text(fill: rgb("555555"))[Dec 2025 – Mar 2026]

  ],
  main-column-second-row: [
    - #strong[Testing Execution:] Executed functional, regression, integration, end-to-end, test execution and UAT testing across SaaS-based finance and digital platforms using Jira and Selenium to ensure test coverage.

    - #strong[Module Validation:] Validated core finance modules, business requirements analysis, expenses, travel, cost allocation, taxation, budgeting, and approval workflows ensuring accurate business logic and UX validation.

    - #strong[Defect Management:] Handled 158+ defects, 110+ enhancements, and 38+ feature improvements through defect lifecycle management, validation, and regression cycles to improve stability and performance.

    - #strong[API Testing:] Executed REST API testing using Postman and cURL ensuring API validation and request handling workflow.

    - #strong[Team Collaboration:] Collaborated with developers and product managers on root cause analysis and bug tracking.

    - #strong[Test Documentation:] Maintained test cases, test execution reports, and UAT test documentation supporting releases.

    - #strong[Experience Letter:] #link("https://drive.google.com/file/d/1pUutV1hiyrfaR4c-3nxJm2eRJRQJkb/view")[https://drive.google.com/file/d/1pUutV1hiyrfaR4c-3nxJm2eRJRQJkb/view]

  ],
)

#regular-entry(
  [
    #text(fill: rgb("1f4e79"))[•] #text(fill: rgb("2e75b6"))[#strong[Sherwa.Tech]], Indore --- #emph[Software Developer and Backend Engineer Intern]

  ],
  [
    #text(fill: rgb("555555"))[May 2024 – Jul 2024]

  ],
  main-column-second-row: [
    - #strong[System Architecture:] Architected scalable web apps using React, Redux Toolkit, REST APIs, and JavaScript.

    - #strong[Backend Operations:] Engineered REST APIs using Node.js, Express.js, and MongoDB defining API contracts and CRUD operations.

    - #strong[Engineering Documentation:] Authored test documentation and environment configuration improving code quality by 28\%.

    - #strong[Project Delivery:] Resolved technical issues ensuring 100\% on-time delivery and performance optimization.

    - #strong[Agile Collaboration:] Collaborated in a 7-member Agile Scrum team using GitHub improving efficiency by 59\%.

    - #strong[Experience Letter:] #link("https://drive.google.com/file/d/1TBx02yV3JcBhmlmX3pT21OFPSRCXACPG/")[https://drive.google.com/file/d/1TBx02yV3JcBhmlmX3pT21OFPSRCXACPG/]

  ],
)

== Projects

#regular-entry(
  [
    #text(fill: rgb("1f4e79"))[•] #text(fill: rgb("2e75b6"))[#strong[Mini Tool App]] --- #emph[Web Developer and Frontend Engineer | PWA, Chrome Extension]

  ],
  [
    #text(fill: rgb("555555"))[Jan 2026 – Mar 2026]

  ],
  main-column-second-row: [
    - #strong[Architecture:] Designed modular architecture using MVC design and high scalability.

    - #strong[API:] Implemented API integration with request handling, response handling, and robust error handling.

    - #strong[Performance:] Optimized performance using efficient routing, dynamic loading, and execution pipelines.

    - #strong[Feature:] Developed client-side features using Agile Scrum and version control workflows.

    - #strong[Deployment:] #link("https://udayraj2003.github.io/mini-tool-app/")[https://udayraj2003.github.io/mini-tool-app/]

  ],
)

#regular-entry(
  [
    #text(fill: rgb("1f4e79"))[•] #text(fill: rgb("2e75b6"))[#strong[StudyNotion]] --- #emph[Full Stack Software Engineer | React.js, Node.js, MongoDB, Cloudinary]

  ],
  [
    #text(fill: rgb("555555"))[May 2025 – Jul 2025]

  ],
  main-column-second-row: [
    - #strong[Platform:] Developed MERN ed-tech platform enabling authentication, API integration, and ratings.

    - #strong[System Architecture:] Designed system architecture using React, Node, Express REST APIs, and MongoDB.

    - #strong[Security:] Implemented JWT authentication, OTP login, and middleware-based course management.

    - #strong[Media Integration:] Integrated Cloudinary storage and REST APIs enabling API validation and user workflows.

    - #strong[Deployment:] #link("https://studynotion-ochre.vercel.app/")[https://studynotion-ochre.vercel.app/]

  ],
)

== Education

#education-entry(
  [
    #text(fill: rgb("1f4e79"))[•] #text(fill: rgb("2e75b6"))[#strong[Shri G.S. Institute of Technology and Science]], Indore --- #emph[Bachelor of Technology (B.Tech)]

  ],
  [
    #text(fill: rgb("555555"))[2022 – 2026]

  ],
  main-column-second-row: [
    Electronics and Telecommunication Engineering — CGPA: 7.8

  ],
)

== Achievements

• #strong[Competitive Coding:] Solved 275+ DSA problems on LeetCode, Codeforces and Geeks for Geeks.

• #strong[JEE Score:] Secured AIR under 59K out of 1.2 Million, ranking among top 6.48\% of candidates.

== Certifications

• #strong[Problem Solving:] HackerRank Certification — #link("https://hackerrank.com/certificates/9119dec96173/")[https://hackerrank.com/certificates/9119dec96173/]

• #strong[SQL:] HackerRank Certification — #link("https://hackerrank.com/certificates/ea29a9789622/")[https://hackerrank.com/certificates/ea29a9789622/]

• #strong[Machine Learning and Deep Learning:] NPTEL — #link("https://drive.google.com/file/d/1Eo3PFcqcSIUyh5Wmv5-vFc11R6meGDzn/")[https://drive.google.com/file/d/1Eo3PFcqcSIUyh5Wmv5-vFc11R6meGDzn/]
