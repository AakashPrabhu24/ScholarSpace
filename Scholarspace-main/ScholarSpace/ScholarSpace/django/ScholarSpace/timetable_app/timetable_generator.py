from datetime import date, datetime

from django.utils import timezone

class TimetableGenerator:
    def __init__(self, form_data):
        self.form_data = form_data
        self.subjects = self._get_subjects()
        if not self.subjects:
            self.subjects = [{'name': 'General study', 'level': 50, 'type': 'subject'}]
        self.available_hours_per_day = self._calculate_available_hours()
        self.exam_days_left = self._calculate_days_to_exam()
        
    def _get_subjects(self):
        """Extract subjects and their preparation levels from form data"""
        subjects = []
        
        # Add languages
        if self.form_data.get('language1_name') and self.form_data.get('language1_level') is not None:
            subjects.append({
                'name': self.form_data['language1_name'],
                'level': self.form_data['language1_level'],
                'type': 'language'
            })
            
        if self.form_data.get('language2_name') and self.form_data.get('language2_level') is not None:
            subjects.append({
                'name': self.form_data['language2_name'],
                'level': self.form_data['language2_level'],
                'type': 'language'
            })
        
        # Add other subjects
        for i in range(1, 5):
            if self.form_data.get(f'subject{i}_name') and self.form_data.get(f'subject{i}_level') is not None:
                subjects.append({
                    'name': self.form_data[f'subject{i}_name'],
                    'level': self.form_data[f'subject{i}_level'],
                    'type': 'subject'
                })
        
        return subjects
    
    def _calculate_available_hours(self):
        """Calculate available study hours per day"""
        # Start with 24 hours
        total_hours = 24
        
        # Subtract daily unavoidable activities (sleep, eating, etc.)
        unavoidable_hours = self.form_data.get('daily_activities_hours', 0)
        total_hours -= unavoidable_hours
        
        # Subtract job hours if any
        if self.form_data.get('job_status') in ['part_time', 'full_time']:
            job_hours = self.form_data.get('job_hours') or 0
            total_hours -= job_hours

        # Subtract class hours if attending classes
        if self.form_data.get('attending_classes'):
            class_hours = self.form_data.get('class_hours') or 0
            total_hours -= class_hours
        
        return max(total_hours, 1)  # Ensure at least 1 hour is available
    
    def _calculate_days_to_exam(self):
        """Calculate days remaining until exam"""
        if not self.form_data.get('preparing_for_exam'):
            # If not preparing for an exam, default to 30 days
            return 30
        
        exam_raw = self.form_data.get('exam_date')
        if not exam_raw:
            return 30

        try:
            if isinstance(exam_raw, datetime):
                exam_date = exam_raw.date()
            elif isinstance(exam_raw, date):
                exam_date = exam_raw
            elif isinstance(exam_raw, str):
                exam_date = datetime.strptime(exam_raw, '%Y-%m-%d').date()
            else:
                return 30
            today = timezone.now().date()
            days_to_exam = (exam_date - today).days
            return max(days_to_exam, 1)
        except (ValueError, TypeError):
            return 30
    
    def _allocate_hours_to_subjects(self):
        """Allocate study hours to subjects based on preparation level"""
        if not self.subjects:
            return {}
        
        # Calculate total weighted need (100 - level)
        total_need = sum(100 - subject['level'] for subject in self.subjects)
        
        # If all subjects are 100% prepared, allocate equally
        if total_need == 0:
            hours_per_subject = {subject['name']: 1 for subject in self.subjects}
            return hours_per_subject
        
        # Allocate hours based on need
        available_hours = self.available_hours_per_day
        hours_per_subject = {}
        
        for subject in self.subjects:
            need = 100 - subject['level']
            # Allocate proportional hours
            subject_hours = (need / total_need) * available_hours
            hours_per_subject[subject['name']] = round(subject_hours, 1)
        
        return hours_per_subject
    
    def _format_duration(self, hours):
        """Format duration in hours and minutes"""
        total_minutes = int(hours * 60)
        hours_part = total_minutes // 60
        minutes_part = total_minutes % 60
        # Combine hours and minutes into a single value
        return f"{hours_part}:{minutes_part:02d} hours"
    
    def generate_timetable(self):
        """Generate the timetable"""
        hours_per_subject = self._allocate_hours_to_subjects()
        effective_days = self.exam_days_left - self.form_data.get('force_majeure_days', 0) - self.form_data.get('revision_days', 0)
        
        # Ensure we have at least 1 effective day
        effective_days = max(effective_days, 1)
        
        # Generate daily timetable
        daily_schedule = []
        
        # Determine start hour based on preference
        start_hour = 8  # Default for day
        if self.form_data.get('study_preference') == 'night':
            start_hour = 18
        elif self.form_data.get('study_preference') == 'both':
            # Split between morning and evening
            morning_start = 7
            evening_start = 18
            
            # Divide subjects between morning and evening
            morning_subjects = self.subjects[:len(self.subjects)//2]
            evening_subjects = self.subjects[len(self.subjects)//2:]
            
            current_hour = morning_start
            for subject in morning_subjects:
                subject_hours = hours_per_subject.get(subject['name'], 1)
                end_hour = current_hour + subject_hours
                
                # Handle end_hour that exceeds 24
                display_end_hour = end_hour
                if display_end_hour >= 24:
                    display_end_hour -= 24
                
                daily_schedule.append({
                    'start_time': f"{int(current_hour):02d}:00",
                    'end_time': f"{int(display_end_hour):02d}:{int((display_end_hour % 1) * 60):02d}",
                    'subject': subject['name'],
                    'duration': self._format_duration(subject_hours)
                })
                current_hour = end_hour
            
            current_hour = evening_start
            for subject in evening_subjects:
                subject_hours = hours_per_subject.get(subject['name'], 1)
                end_hour = current_hour + subject_hours
                
                # Handle end_hour that exceeds 24
                display_end_hour = end_hour
                if display_end_hour >= 24:
                    display_end_hour -= 24
                
                daily_schedule.append({
                    'start_time': f"{int(current_hour):02d}:00",
                    'end_time': f"{int(display_end_hour):02d}:{int((display_end_hour % 1) * 60):02d}",
                    'subject': subject['name'],
                    'duration': self._format_duration(subject_hours)
                })
                current_hour = end_hour
            
            # Sort by start time
            daily_schedule.sort(key=lambda x: x['start_time'])
            return {
                'daily_schedule': daily_schedule,
                'effective_days': effective_days,
                'revision_days': self.form_data.get('revision_days', 0),
                'force_majeure_days': self.form_data.get('force_majeure_days', 0),
                'exam_days_left': self.exam_days_left,
                'available_hours': self.available_hours_per_day
            }
        
        # For single time preference (day or night)
        current_hour = start_hour
        for subject in self.subjects:
            subject_hours = hours_per_subject.get(subject['name'], 1)
            end_hour = current_hour + subject_hours
            
            # Handle end_hour that exceeds 24
            display_end_hour = end_hour
            if display_end_hour >= 24:
                display_end_hour -= 24
            
            daily_schedule.append({
                'start_time': f"{int(current_hour):02d}:00",
                'end_time': f"{int(display_end_hour):02d}:{int((display_end_hour % 1) * 60):02d}",
                'subject': subject['name'],
                'duration': self._format_duration(subject_hours)
            })
            current_hour = end_hour
        
        return {
            'daily_schedule': daily_schedule,
            'effective_days': effective_days,
            'revision_days': self.form_data.get('revision_days', 0),
            'force_majeure_days': self.form_data.get('force_majeure_days', 0),
            'exam_days_left': self.exam_days_left,
            'available_hours': self.available_hours_per_day
        }