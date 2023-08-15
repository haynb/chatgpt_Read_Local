from flask import Flask, request,jsonify,Response,make_response,stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
import os,threading
from queue import Queue


from  web_chat import Ai,Fdb,Chat_with_file,MyCustomHandler,File


app = Flask(__name__)
CORS(app)  # 启用CORS
socketio = SocketIO(app)  # 启用socketio
app.config['UPLOAD_FOLDER'] = 'upload'

# 实例化chat
Ai = Ai()
# 实例化数据库
this_db = Fdb(embeddings=Ai.embeddings,path=app.config['UPLOAD_FOLDER'])
# 实例化文件
this_file = File()
# 实例化文件聊天
Chat_with_file = Chat_with_file(Ai.llm,this_db.db.as_retriever())
file_qa = Chat_with_file.qa







@app.route('/check_file', methods=['GET'])
def check_file():
    folder = app.config['UPLOAD_FOLDER']
    return jsonify(this_file.check_file(folder))

@app.route('/delete_file', methods=['POST'])
def delete_file():
    name = request.get_json()
    file_name = name['file_name']
    try:
        this_file.delete_file(os.path.join(app.config['UPLOAD_FOLDER'], str(file_name)))
        this_db.fresh()
        return jsonify('delete success!')
    except Exception as e:
        return jsonify('delete failed:'+str(e))









@app.route('/upload', methods=['POST'])
def upload_file():
    # 检测是否有文件被上传
    if 'file' not in request.files:
        return make_response(jsonify('no files in post'), 405)
    file = request.files['file']
    filename = secure_filename(file.filename)
    load_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        this_file.add_file(file,load_path)
        this_db.add(load_path)
        return make_response(jsonify('file success!'), 200)
    except Exception as e:
        return make_response(jsonify('file upload failed：'+str(e)), 500)


@app.route('/chat_with_file', methods=['POST'])
def chat_with_file():
    # 检测是否存在文件
    if len(os.listdir(app.config['UPLOAD_FOLDER'])) == 0:
        return jsonify('there is no files please upload first,or use chat_without_file')
    data = request.get_json()  # 获取请求体中的JSON数据
    if data and 'message' in data and 'history' in data:
        query = data['message']
        historys = data['history']
        chat_history = [(history["question"], history["answer"]) for history in historys]
        print(chat_history)
        print(f"Received message: {query}")
        # 在这里处理消息
        doc = this_db.search(query)
        # result = file_qa({"question": query, "chat_history": chat_history})
        result = file_qa.run(input_documents=doc, question=query )
        print(result)
        return jsonify(result)
    else:
        return jsonify('failed to get your message!')





# @app.route('/chat_with_file_streaming', methods=['POST'])
# def chat_with_file_streaming():
#     # 检测是否存在文件
#     if len(os.listdir(app.config['UPLOAD_FOLDER'])) == 0:
#         return jsonify('there is no files please upload first,or use chat_without_file')
#     data = request.get_json()  # 获取请求体中的JSON数据
#     if data and 'message' in data and 'history' in data:
#         query = data['message'] + ".... tell me all about this!!!!!!"
#         historys = data['history']
#         chat_history = [(history["question"], history["answer"]) for history in historys]
#         print(f"Received message: {query}")
#         def worker():
#             result = file_qa.run(question=query, chat_history=chat_history,
#                           callbacks=[MyCustomHandler(queue)])
#             pass
#         def generate():
#             while thread.is_alive():
#                 if not queue.empty():
#                     yield queue.get()
#         thread = threading.Thread(target=worker, daemon=True)
#         thread.start()
#         return app.response_class(stream_with_context(generate()))
#     else:
#         return jsonify('failed to get your message!')


# 创建一个字典，用于存储每个请求的队列和处理程序
request_handlers = {}

@app.route('/chat_with_file_streaming', methods=['POST'])
def chat_with_file_streaming():
    # 检测是否存在文件
    if len(os.listdir(app.config['UPLOAD_FOLDER'])) == 0:
        return jsonify('there is no files please upload first,or use chat_without_file')
    data = request.get_json()  # 获取请求体中的JSON数据
    if data and 'message' in data and 'history' in data:
        query = data['message'] + ".... tell me all about this!!!!!!"
        historys = data['history']
        chat_history = [(history["question"], history["answer"]) for history in historys]
        print(f"Received message: {query}")
        queue = Queue()  # 创建一个独立的队列
        request_handlers[queue] = MyCustomHandler(queue)  # 创建一个独立的处理程序
        thread = threading.Thread(target=worker, args=(query, chat_history, queue), daemon=True)
        thread.start()
        return app.response_class(stream_with_context(generate(thread, queue)))
    else:
        return jsonify('failed to get your message!')

def worker(query, chat_history, queue):
    result = file_qa.run(question=query, chat_history=chat_history,
                         callbacks=[request_handlers[queue]])

def generate(thread, queue):
    while True:
        if not queue.empty():
            yield queue.get()
        elif not thread.is_alive():
            del request_handlers[queue]  # 删除已完成的请求的队列和处理程序
            break


@app.route('/chat_without_file', methods=['POST'])
def chat_without_file():
    data = request.get_json()  # 获取请求体中的JSON数据
    if data and 'message' in data and 'history' in data:
        query = data['message'] + ",,tell me all!!"
        chat_history = data['history']
        print(f"Received message: {query}")
        # 在这里处理消息
        try:
            result = file_qa({"question": query, "chat_history": chat_history})
        except Exception as e:
            return jsonify('文件聊天失败,错误：'+str(e))
        return  jsonify(result)
    else:
        return jsonify('please check your message')






if __name__ == '__main__':
    app.run(host='0.0.0.0')
