// Team info for the About page. Edit freely.
// Photos: drop <photo>.jpg into src/assets/team/ (e.g. carson.jpg) and it shows up
// automatically. Until then, the card shows initials.

export interface TeamMember {
  name: string
  role: string
  shortRole: string // the small caps label on the capsule
  photo: string // file name without extension, in src/assets/team/
  initials: string
  blurb: string
}

export const STUDENTS: TeamMember[] = [
  {
    name: 'Carson Fulmer',
    role: 'PM & Full Stack Developer',
    shortRole: 'PM & Full Stack',
    photo: 'carson',
    initials: 'CF',
    blurb: 'Led the project as PM, running the roadmap and sprints. Pioneered the AI claim normalization and research overview, and set up CI and SonarCloud.',
  },
  {
    name: 'NJ Lacambra',
    role: 'UI/UX Design',
    shortRole: 'UI/UX Design',
    photo: 'nj',
    initials: 'NJ',
    blurb: 'Led UI/UX and brand design, from the Figma prototype to the finished interface. Built the frontend, including search, the study clipboards, and the design system.',
  },
  {
    name: 'Ishan Kumthekar',
    role: 'Full Stack Developer',
    shortRole: 'Full Stack',
    photo: 'ishan',
    initials: 'IK',
    blurb: 'Owned the data layer. Built the PostgreSQL storage for claim matching, saved examples, and the result cache that keeps searches fast.',
  },
  {
    name: 'Joseph Patriarca',
    role: 'Back End Developer',
    shortRole: 'Back End',
    photo: 'joey',
    initials: 'JP',
    blurb: 'Led backend development, from the FastAPI foundation to the PubMed client and Crossref retraction checks. Drove testing and CI coverage.',
  },
]

export const ADVISOR: TeamMember & { title: string } = {
  name: 'Amber Emanuel, Ph.D.',
  role: 'Advising Professor',
  shortRole: 'Advising Professor',
  title: 'Instructional Associate Professor, Department of Health Education & Behavior',
  photo: 'amber',
  initials: 'AE',
  blurb: 'Advises on health science and how evidence is presented, and reviews the design for clarity.',
}

export const SUPERVISOR: TeamMember & { title: string } = {
  name: 'Georgie',
  role: 'Project Supervisor',
  shortRole: 'Project Supervisor',
  title: 'Head of Human Resources, Chief Supervision Officer',
  photo: 'georgie', // src/assets/team/georgie.jpg
  initials: '🐕',
  blurb: 'Leads people operations: enforces attendance at every meeting, mediates team conflicts, and conducts performance reviews. Champions employee wellness through mandatory walk breaks. Compensation: treats.',
}

// The interns, each tied to a student by `owner`. Photos are src/assets/team/<photo>.jpg.
// Names, roles and blurbs are drafts: edit freely.
export interface Intern extends TeamMember {
  owner: string // must match a STUDENTS name exactly
}

export const INTERNS: Intern[] = [
  {
    name: 'Intern Fulmer',
    owner: 'Carson Fulmer',
    role: 'Morale Intern',
    shortRole: 'Morale Intern',
    photo: 'internfulmer',
    initials: 'IF',
    blurb: 'Greets every standup with maximum enthusiasm. Handles team morale and outdoor testing. Compensation: belly rubs.',
  },
  {
    name: 'Intern Lacambra',
    owner: 'NJ Lacambra',
    role: 'Quality Assurance Intern',
    shortRole: 'Quality Assurance',
    photo: 'internlacambra',
    initials: 'IL',
    blurb: 'Inspects every screen and snack up close. Sniffs out bugs before they reach production. Boops on request.',
  },
  {
    name: 'Intern Kumthekar',
    owner: 'Ishan Kumthekar',
    role: 'Security Intern',
    shortRole: 'Security',
    photo: 'internkumthekar',
    initials: 'IK',
    blurb: 'Monitors the window around the clock for threats. Does not acknowledge deadlines. Compensation: treats, on their own schedule.',
  },
  {
    name: 'Intern Patriarca',
    owner: 'Joseph Patriarca',
    role: 'Rest & Recovery Intern',
    shortRole: 'Rest & Recovery',
    photo: 'internpatriarca',
    initials: 'IP',
    blurb: 'Leads by example on the importance of rest. Frequently found napping on the job. Compensation: more naps.',
  },
]

export const REPO_URL = 'https://github.com/carsonful/SecondOpinion'