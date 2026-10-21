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
    blurb: 'Runs the roadmap and sprints, set up CI and SonarCloud, designed the evidence grading method.',
  },
  {
    name: 'NJ Lacambra',
    role: 'UI/UX Design',
    shortRole: 'UI/UX Design',
    photo: 'nj',
    initials: 'NJ',
    blurb: 'Designed the Figma prototype and brand, built the frontend screens and design system.',
  },
  {
    name: 'Ishan Kumthekar',
    role: 'Full Stack Developer',
    shortRole: 'Full Stack',
    photo: 'ishan',
    initials: 'IK',
    blurb: 'Claim normalization and matching, PostgreSQL storage, the PubMed ingestion pipeline.',
  },
  {
    name: 'Joseph Patriarca',
    role: 'Back End Developer',
    shortRole: 'Back End',
    photo: 'joey',
    initials: 'JP',
    blurb: 'Set up the FastAPI backend and health check, backend tests and coverage in CI.',
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

export const REPO_URL = 'https://github.com/carsonful/SecondOpinion'