const iconPath = (fileName: string) => `/assets/icons/muyi/${fileName}`

export const appIcons = {
  home: iconPath('home-deer.png'),
  franchise: iconPath('franchise-deer.png'),
  courses: iconPath('course-note.png'),
  myCourses: iconPath('my-courses.png'),
  schedule: iconPath('schedule.png'),
  headphones: iconPath('headphones.png'),
  teacher: iconPath('teacher.png'),
  profile: iconPath('profile.png'),
  franchiseBrand: iconPath('franchise-deer-alt.png'),
} as const
