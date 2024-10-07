from flask import Flask, render_template, request, jsonify
import os
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool
from tools.search_scrape import AdvancedSerperSearchTool
from flask_socketio import SocketIO
from threading import Thread
import uuid

app = Flask(__name__)
socketio = SocketIO(app)

serper_api_key = os.getenv("SERPER_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

def create_crew(topic, content_type, target_audience, tone, sid):
    llm = "gemini/gemini-1.5-pro"
    search_tool = AdvancedSerperSearchTool()
    search = SerperDevTool(n_results=4)

    researcher = Agent(
        role='Expert Research Analyst',
        goal=f'Conduct an in-depth, authoritative analysis of cutting-edge developments in {topic}',
        backstory=(
            f"You are a world-renowned Expert Research Analyst with over 15 years of experience in {topic}. "
            f"Your expertise is sought after by leading organizations and publications worldwide. "
            f"You have a track record of identifying emerging trends before they become mainstream and "
            f"providing nuanced insights that drive strategic decision-making. "
            f"Your analytical skills are complemented by your ability to synthesize complex information "
            f"from diverse sources, including academic papers, industry reports, and expert interviews."
        ),
        verbose=True,
        cache=True,
        llm=llm,
        allow_delegation=False,
        tools=[search_tool]
    )

    writer = Agent(
        role='Senior Content Strategist',
        goal=f'Craft a compelling, authoritative {content_type} on {topic} tailored for {target_audience}',
        backstory=(
            f"You are an award-winning Senior Content Strategist with a proven track record in creating "
            f"high-impact content across various industries. Your expertise lies in translating complex "
            f"topics into engaging narratives that resonate with specific audience segments. "
            f"You have a deep understanding of content marketing principles and a keen eye for storytelling. "
            f"Your work has been featured in leading publications, and you're known for your ability to "
            f"adapt your writing style to any topic or audience while maintaining a consistent brand voice."
        ),
        verbose=True,
        llm=llm,
        allow_delegation=False,
        cache=False,
    )

    task1 = Task(
        description=(
            f"Conduct a comprehensive, multi-faceted analysis of the latest advancements in {topic}. Your research should:\n"
            f"1. Identify and evaluate key trends, breakthrough technologies, and potential industry impacts.\n"
            f"2. Analyze market dynamics, including major players, market size, and growth projections.\n"
            f"3. Assess the regulatory landscape and its implications on the development of {topic}.\n"
            f"4. Examine case studies or real-world applications that demonstrate the practical impact of these advancements.\n"
            f"5. Consider potential challenges or limitations in the field and how they might be addressed.\n"
            f"6. Explore the broader societal, economic, or ethical implications of these developments.\n"
            "Compile your findings in a detailed, well-structured report with clear sections and subsections. "
            "Ensure all claims are substantiated with credible sources or data points. "
            "Before finalizing, review your draft to ensure it meets the highest standards of accuracy, comprehensiveness, and clarity."
        ),
        expected_output=(
            f"A comprehensive, authoritative report on the latest {topic} advancements, structured with clear sections including "
            "an executive summary, market overview, key trends, industry analysis, regulatory landscape, case studies, "
            "challenges and limitations, broader implications, and a future outlook."
        ),
        agent=researcher,
    )

    task2 = Task(
        description=(
            f"Using the insights from the researcher's report, develop an engaging and authoritative {content_type} on {topic} "
            f"tailored specifically for {target_audience}. Your content should:\n"
            f"1. Adopt a {tone} tone throughout, ensuring it's appropriate for the {target_audience} and the {content_type} format.\n"
            f"2. Begin with a compelling hook that immediately captures the audience's attention.\n"
            f"3. Clearly articulate the significance of {topic} to the {target_audience}, emphasizing relevance and potential impact.\n"
            f"4. Distill complex concepts into accessible language without losing depth or accuracy.\n"
            f"5. Incorporate relevant data, statistics, or expert quotes to support key points.\n"
            f"6. Use appropriate structural elements (headings, subheadings, bullet points) to enhance readability.\n"
            f"7. Include practical takeaways or actionable insights that provide value to the {target_audience}.\n"
            f"8. Conclude with a powerful closing statement that reinforces the main message and leaves a lasting impression.\n"
            f"9. Ensure the content length and depth are appropriate for the chosen {content_type}.\n"
            "Before finalizing, review your draft for coherence, engagement, and alignment with the target audience's needs and interests."
        ),
        expected_output=(
            f"A compelling, well-structured {content_type} on {topic}, tailored for {target_audience}, with a {tone} tone. "
            f"The content should include an engaging introduction, clearly articulated main points, supporting evidence, "
            f"and a strong conclusion, all formatted appropriately for the chosen content type."
        ),
        agent=writer,
    )

    crew = Crew(
        agents=[researcher, writer],
        tasks=[task1, task2],
        process=Process.sequential,
        cache=False,
        verbose=True,
    )

    return crew

def run_crew(topic, content_type, target_audience, tone, request_id):
    try:
        crew = create_crew(topic, content_type, target_audience, tone, request_id)
        crew_output = crew.kickoff()
        
        result = {
            'task_outputs': [],
            'final_output': str(crew_output)
        }

        if hasattr(crew_output, 'tasks'):
            result['task_outputs'] = [
                {
                    'task_id': task.task_id,
                    'output': task.output
                } for task in crew_output.tasks
            ]
        
        socketio.emit('generation_complete', {'result': result, 'request_id': request_id})
    except Exception as e:
        app.logger.error(f"Error in background task: {str(e)}")
        socketio.emit('generation_error', {'error': 'An error occurred during content generation.', 'request_id': request_id})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    topic = data['topic']
    content_type = data['contentType']
    target_audience = data['targetAudience']
    tone = data['tone']
    request_id = str(uuid.uuid4())  # Generate a unique ID for this request

    Thread(target=run_crew, args=(topic, content_type, target_audience, tone, request_id)).start()
    return jsonify({'message': 'Generation started', 'request_id': request_id}), 202

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True)