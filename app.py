from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, RadioField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mentortrack.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# データベースモデル
class Mentee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    reports = db.relationship('WeeklyReport', backref='mentee', lazy=True)

class WeeklyReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mentee_id = db.Column(db.Integer, db.ForeignKey('mentee.id'), nullable=False)
    
    # 企画ステージ
    planning_stage = db.Column(db.String(50), nullable=False)  # 提案前/提案済み/発注済み/完了
    
    # 代表商品群
    product_group = db.Column(db.Text, nullable=False)
    
    # 今週の進捗（JSON形式で保存）
    progress_items = db.Column(db.Text)  # チェックリスト項目
    
    # 実施した行動
    actions_taken = db.Column(db.Text)
    
    # 気づき・悩み
    insights_concerns = db.Column(db.Text)
    
    # 自己評価
    self_evaluation = db.Column(db.Integer)  # 1-3
    
    # メンターコメント
    mentor_comment = db.Column(db.Text)
    
    # 追加の問いかけ回答（JSON形式）
    additional_responses = db.Column(db.Text)
    
    # 報告日
    report_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 週の開始日（月曜日）
    week_start = db.Column(db.DateTime, nullable=False)

# フォームクラス
class WeeklyReportForm(FlaskForm):
    planning_stage = SelectField('企画ステージ', 
                                choices=[('proposal_pre', '提案前'), 
                                        ('proposal_post', '提案済み'), 
                                        ('ordered', '発注済み'), 
                                        ('completed', '完了')],
                                validators=[DataRequired()])
    
    product_group = TextAreaField('代表商品群', 
                                 validators=[DataRequired(), Length(min=1, max=500)],
                                 render_kw={'rows': 3, 'placeholder': '今週取り組んだ商品群を記述してください'})
    
    # 進捗チェックリスト（動的に生成）
    progress_items = TextAreaField('今週の進捗', 
                                  render_kw={'rows': 5, 'placeholder': '完了した項目を記述してください'})
    
    actions_taken = TextAreaField('実施した行動', 
                                 render_kw={'rows': 4, 'placeholder': '今週実施した具体的な行動を記述してください'})
    
    insights_concerns = TextAreaField('気づき・悩み', 
                                     render_kw={'rows': 4, 'placeholder': '今週感じた気づきや悩みを自由に記述してください'})
    
    self_evaluation = RadioField('自己評価', 
                                choices=[(1, '1 - 思うように進まなかった'), 
                                        (2, '2 - まあまあ進んだ'), 
                                        (3, '3 - とても順調に進んだ')],
                                validators=[DataRequired()])
    
    mentor_comment = TextAreaField('メンターコメント', 
                                  render_kw={'rows': 3, 'placeholder': 'メンターからのコメント（任意）'})
    
    # 追加の問いかけ
    time_consuming_task = TextAreaField('今週、最も時間を使った作業は？', 
                                       render_kw={'rows': 2, 'placeholder': '（任意）'})
    
    difficult_decision = TextAreaField('今週、最も迷った判断は？', 
                                      render_kw={'rows': 2, 'placeholder': '（任意）'})
    
    learned_from_senior = TextAreaField('今週、先輩から学んだことは？', 
                                       render_kw={'rows': 2, 'placeholder': '（任意）'})
    
    own_decision = TextAreaField('今週、自分の判断で進めたことは？', 
                                render_kw={'rows': 2, 'placeholder': '（任意）'})
    
    redid_task = TextAreaField('今週、やり直したことは？', 
                              render_kw={'rows': 2, 'placeholder': '（任意）'})
    
    submit = SubmitField('報告を保存')

# ルート
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/mentee/<int:mentee_id>')
def mentee_dashboard(mentee_id):
    mentee = Mentee.query.get_or_404(mentee_id)
    reports = WeeklyReport.query.filter_by(mentee_id=mentee_id).order_by(WeeklyReport.report_date.desc()).all()
    return render_template('mentee_dashboard.html', mentee=mentee, reports=reports)

@app.route('/report/new/<int:mentee_id>', methods=['GET', 'POST'])
def new_report(mentee_id):
    mentee = Mentee.query.get_or_404(mentee_id)
    form = WeeklyReportForm()
    
    if form.validate_on_submit():
        # 今週の月曜日を計算
        today = datetime.now()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 追加の問いかけ回答をJSON形式で保存
        additional_responses = {
            'time_consuming_task': form.time_consuming_task.data,
            'difficult_decision': form.difficult_decision.data,
            'learned_from_senior': form.learned_from_senior.data,
            'own_decision': form.own_decision.data,
            'redid_task': form.redid_task.data
        }
        
        report = WeeklyReport(
            mentee_id=mentee_id,
            planning_stage=form.planning_stage.data,
            product_group=form.product_group.data,
            progress_items=form.progress_items.data,
            actions_taken=form.actions_taken.data,
            insights_concerns=form.insights_concerns.data,
            self_evaluation=form.self_evaluation.data,
            mentor_comment=form.mentor_comment.data,
            additional_responses=str(additional_responses),
            week_start=week_start
        )
        
        db.session.add(report)
        db.session.commit()
        flash('週次報告が保存されました！', 'success')
        return redirect(url_for('mentee_dashboard', mentee_id=mentee_id))
    
    return render_template('new_report.html', form=form, mentee=mentee)

@app.route('/report/<int:report_id>')
def view_report(report_id):
    report = WeeklyReport.query.get_or_404(report_id)
    
    # 前週の報告を取得
    previous_week_start = report.week_start - timedelta(days=7)
    previous_report = WeeklyReport.query.filter_by(
        mentee_id=report.mentee_id, 
        week_start=previous_week_start
    ).first()
    
    return render_template('view_report.html', report=report, previous_report=previous_report)

@app.route('/create-sample-mentee', methods=['POST'])
def create_sample_mentee():
    try:
        # 既存のサンプルメンティをチェック
        existing_mentee = Mentee.query.filter_by(email='sample@example.com').first()
        
        if existing_mentee:
            # 既存のサンプルメンティが存在する場合は、そのIDを返す
            return jsonify({
                'success': True,
                'mentee_id': existing_mentee.id,
                'message': '既存のサンプルメンティを使用します'
            })
        else:
            # 新しいサンプルメンティを作成
            sample_mentee = Mentee(
                name='サンプルメンティ',
                email='sample@example.com'
            )
            db.session.add(sample_mentee)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'mentee_id': sample_mentee.id,
                'message': 'サンプルメンティが作成されました'
            })
    except Exception as e:
        # エラーの詳細をログに出力
        print(f"Error creating sample mentee: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'エラーが発生しました: {str(e)}'
        })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
