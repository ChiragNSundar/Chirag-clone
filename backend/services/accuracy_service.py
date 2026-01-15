"""
Accuracy Service - Test and measure how well the clone matches the real user.
Includes A/B testing and self-assessment quizzes.
"""
from typing import Dict, Optional, List
from datetime import datetime
import random

from .llm_service import get_llm_service
from .personality_service import get_personality_service
from .memory_service import get_memory_service
from .logger import get_logger

logger = get_logger(__name__)


class AccuracyService:
    """Service for measuring clone accuracy and authenticity."""
    
    def __init__(self):
        self.llm = get_llm_service()
        self.personality = get_personality_service()
        self.memory = get_memory_service()
        
        self._quiz_history: List[Dict] = []
        self._accuracy_scores: List[float] = []
    
    def generate_quiz(self, num_questions: int = 5) -> Dict:
        """Generate a quiz to test clone accuracy."""
        profile = self.personality.get_profile()
        
        # Get sample training examples for context
        examples = self.memory.get_examples(limit=20)
        
        quiz_types = [
            'preference',  # What would user prefer
            'reaction',    # How would user react
            'style',       # What's user's style
            'knowledge',   # What does user know
            'opinion'      # What's user's opinion
        ]
        
        questions = []
        
        for i in range(num_questions):
            q_type = quiz_types[i % len(quiz_types)]
            question = self._generate_question(q_type, profile, examples)
            if question:
                questions.append(question)
        
        quiz = {
            'id': f"quiz_{datetime.now().timestamp()}",
            'created_at': datetime.now().isoformat(),
            'questions': questions,
            'total_questions': len(questions),
            'status': 'pending'
        }
        
        self._quiz_history.append(quiz)
        return quiz
    
    def _generate_question(self, q_type: str, profile, examples: List[Dict]) -> Optional[Dict]:
        """Generate a single quiz question."""
        prompts = {
            'preference': f"Create a 'would you rather' style question that {profile.name} might have a strong preference on based on their personality.",
            'reaction': f"Create a scenario and ask how {profile.name} would typically react.",
            'style': f"Create a question about {profile.name}'s communication or lifestyle style.",
            'knowledge': f"Create a question testing knowledge about {profile.name}'s interests or expertise.",
            'opinion': f"Create a question about {profile.name}'s likely opinion on a topic."
        }
        
        prompt = f"""{prompts.get(q_type, prompts['preference'])}

Known facts about {profile.name}:
{', '.join(profile.facts[:5])}

Generate a multiple choice question with 4 options (A, B, C, D).
Also identify which answer {profile.name} would likely choose.

Format:
QUESTION: [question text]
A) [option]
B) [option]
C) [option]
D) [option]
CORRECT: [letter]

Generate:"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=200,
                temperature=0.8
            )
            
            # Parse response
            lines = response.strip().split('\n')
            question_text = ""
            options = {}
            correct = ""
            
            for line in lines:
                line = line.strip()
                if line.startswith('QUESTION:'):
                    question_text = line.replace('QUESTION:', '').strip()
                elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                    letter = line[0]
                    options[letter] = line[2:].strip()
                elif line.startswith('CORRECT:'):
                    correct = line.replace('CORRECT:', '').strip().upper()[0]
            
            if question_text and len(options) == 4 and correct:
                return {
                    'id': f"q_{datetime.now().timestamp()}_{random.randint(1000, 9999)}",
                    'type': q_type,
                    'question': question_text,
                    'options': options,
                    'correct_answer': correct
                }
            
        except Exception as e:
            logger.error(f"Question generation error: {e}")
        
        return None
    
    def submit_quiz_answers(self, quiz_id: str, answers: Dict[str, str]) -> Dict:
        """Submit answers for a quiz and calculate score."""
        # Find quiz
        quiz = None
        for q in self._quiz_history:
            if q.get('id') == quiz_id:
                quiz = q
                break
        
        if not quiz:
            return {'error': 'Quiz not found'}
        
        # Score answers
        correct = 0
        total = len(quiz['questions'])
        results = []
        
        for question in quiz['questions']:
            q_id = question['id']
            user_answer = answers.get(q_id, '').upper()
            correct_answer = question['correct_answer']
            is_correct = user_answer == correct_answer
            
            if is_correct:
                correct += 1
            
            results.append({
                'question_id': q_id,
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct
            })
        
        score = (correct / total * 100) if total > 0 else 0
        
        # Update quiz status
        quiz['status'] = 'completed'
        quiz['score'] = score
        quiz['results'] = results
        
        # Track accuracy
        self._accuracy_scores.append(score)
        
        return {
            'quiz_id': quiz_id,
            'score': round(score, 1),
            'correct': correct,
            'total': total,
            'results': results
        }
    
    def get_accuracy_stats(self) -> Dict:
        """Get overall accuracy statistics."""
        if not self._accuracy_scores:
            return {
                'quizzes_taken': 0,
                'average_score': 0,
                'best_score': 0,
                'recent_trend': 'no data'
            }
        
        avg = sum(self._accuracy_scores) / len(self._accuracy_scores)
        
        # Calculate trend
        trend = 'stable'
        if len(self._accuracy_scores) >= 3:
            recent = self._accuracy_scores[-3:]
            if recent[-1] > recent[0]:
                trend = 'improving'
            elif recent[-1] < recent[0]:
                trend = 'declining'
        
        return {
            'quizzes_taken': len(self._accuracy_scores),
            'average_score': round(avg, 1),
            'best_score': max(self._accuracy_scores),
            'worst_score': min(self._accuracy_scores),
            'recent_trend': trend,
            'accuracy_grade': self._get_grade(avg)
        }
    
    def _get_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return 'A - Excellent Clone!'
        elif score >= 80:
            return 'B - Good Match'
        elif score >= 70:
            return 'C - Needs Training'
        elif score >= 60:
            return 'D - More Data Needed'
        else:
            return 'F - Keep Training!'
    
    def get_quiz_history(self, limit: int = 10) -> List[Dict]:
        """Get recent quiz history."""
        return self._quiz_history[-limit:]
    
    def generate_ab_test(self, context: str) -> Dict:
        """Generate an A/B test - real response vs clone response."""
        profile = self.personality.get_profile()
        
        # Generate clone response
        prompt = f"""As {profile.name}'s clone, respond to this context:

Context: "{context}"

Respond naturally as {profile.name} would:"""

        try:
            clone_response = self.llm.generate(
                prompt=prompt,
                max_tokens=200,
                temperature=0.8
            ).strip()
            
            return {
                'id': f"ab_{datetime.now().timestamp()}",
                'context': context,
                'clone_response': clone_response,
                'instruction': "Have the real user write their response, then compare!",
                'created_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"A/B test error: {e}")
            return {'error': str(e)}


# Singleton instance
_accuracy_service: Optional[AccuracyService] = None


def get_accuracy_service() -> AccuracyService:
    """Get the singleton accuracy service instance."""
    global _accuracy_service
    if _accuracy_service is None:
        _accuracy_service = AccuracyService()
    return _accuracy_service
