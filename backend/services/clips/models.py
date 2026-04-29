from pydantic import BaseModel


class VideoMetadata(BaseModel):
    youtube_video_id: str
    title: str
    duration_seconds: int


class TranscriptCue(BaseModel):
    start: float
    end: float
    text: str


class CandidateClip(BaseModel):
    start_seconds: float
    end_seconds: float
    hype_score: float
    hype_reasoning: str
    transcript_excerpt: str

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds
