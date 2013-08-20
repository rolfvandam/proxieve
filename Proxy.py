import socket, thread, select, re, zlib, gzip, StringIO, sys, code

BUFLEN=65536

class Proxy:

    def proxy_dummy(self, message):
        return

    proxy_hook = proxy_dummy
       
    def setHook(self, func):
        self.proxy_hook = func
        
    def unhook(self):
        self.proxy_hook = self.proxy_dummy

    def connect_remote(self, host):
        i = host.find(':')
        if i!=-1:
            port = int(host[i+1:])
            host = host[:i]
        else:
            port = 80
        (soc_family, _, _, _, address) = socket.getaddrinfo(host, port)[0]
        remote = socket.socket(soc_family)
        remote.connect(address)
    
        return remote

    def receive(self, sock, length):
        message=""
        buffer=""
    
        while 1:
            buffer=sock.recv(BUFLEN)
            message+=buffer
            if not len(message) < length:
                break;
            
        return message
    
    def receive_header(self, sock):
        message=""
        buffer=""
    
        while 1:
            buffer=sock.recv(BUFLEN)
            message+=buffer
            if message.find("\r\n\r\n") != -1:
                break;
            
        return message

    def get_headerfield(self, headername,buffer):
        m = re.search(headername+": (.*?)\r?\n", buffer, re.I)
        if m:
            return m.group(1)
        else:
            return None
    
    def get_headerfields(self, headername,buffer):
        return re.findall(headername+": (.*?)\r?\n", buffer, re.I)
    
        
    def handle_chunked(self, client, remote, buffer, gzipped=True):
        
        while buffer[buffer.find("\r\n\r\n")+4:].find("\r\n") == -1:
            buffer += remote.recv(BUFLEN)
        
        header = buffer[:buffer.find("\r\n\r\n")+4]
        client.sendall(header)
    
        start_chunk = buffer[buffer.find("\r\n\r\n")+4:]
        data = ""
        
        while 1:
            hex_size = start_chunk[:start_chunk.find("\r\n")]
        
            size = int(hex_size,16)
        
            if not size:
                client.sendall("0\r\n\r\n")
                client.close()
                break;
        
            chunk_body = start_chunk[start_chunk.find("\r\n")+2:]
        
            while size > len(chunk_body):
                rcpt = remote.recv(BUFLEN)
                chunk_body += rcpt
        
            one_chunk = hex_size+"\r\n"+chunk_body[:size]+"\r\n"
        
            client.sendall(one_chunk)
        
            buffer = chunk_body[size:]
            chunk = chunk_body[:size]
                
            data += chunk
        
            while buffer[buffer.find("\r\n")+2:].find("\r\n") == -1:
                buffer += remote.recv(BUFLEN)
            
            start_chunk = buffer[buffer.find("\r\n")+2:]

        if gzipped:
            data = gzip.GzipFile(fileobj=StringIO.StringIO(data), mode="r").read()
    
        return data
    
    
    def receive_remainder(self, sock, header, buffer):

        if header.lower().find("Content-Length".lower()):
            length = self.get_headerfield("Content-Length", header)
            if not length:
                return ""
            total_length = len(header)+int(length)
            if len(buffer) < total_length:
                remainder_length = total_length - len(buffer)
                return self.receive(sock, remainder_length)
    
        return ""    
    
    def handler_t(self, *args):
    
        try:
            self.handler(*args)
        except socket.error:
            print "socket error"

    
    def handler(self, client, address, *args):

        buffer = self.receive_header(client)
        header = buffer[:buffer.find("\r\n\r\n")+4]
        method = buffer[:buffer.find(" ")]
    
        remote_hostname = self.get_headerfield("Host",header)
        remote = self.connect_remote(remote_hostname)
        
        r_buffer = buffer.replace(method+" http://"+remote_hostname+"/", method.upper()+" /")
        r_header = header.replace(method+" http://"+remote_hostname+"/", method.upper()+" /")
        r_buffer += self.receive_remainder(client, header, buffer)
        
        if method.lower() == "post":
            m = re.search("POST (.*?) HTTP", r_header, re.I)
            url = m.group(1)
        
        self.proxy_hook(r_buffer)
        remote.send(r_buffer)
    
        buffer = self.receive_header(remote)
        header = buffer[:buffer.find("\r\n\r\n")+4]
    
        transfer_encoding = self.get_headerfield("Transfer-encoding", header)
        content_encoding = self.get_headerfield("Content-encoding", header)
    
        if transfer_encoding:
            if transfer_encoding.lower() == "chunked":
                if content_encoding == "gzip":
                    data = self.handle_chunked(client, remote, buffer)
                else:
                    data = self.handle_chunked(client, remote, buffer,gzipped=False)
                  
                self.proxy_hook(header+data)
                return

        buffer += self.receive_remainder(remote, header, buffer)
        data = buffer[buffer.find("\r\n\r\n")+4:]
        if content_encoding == "gzip":
            data = gzip.GzipFile(fileobj=StringIO.StringIO(data), mode="r").read()
        
        self.proxy_hook(header+data)
        client.sendall(buffer)
    
    def startProxy(self):
        thread.start_new_thread(self.start_server, ())
    
    def start_server(self, host="0.0.0.0", port=8080, IPv6=False, timeout=60):
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        soc.bind((host, port))
        soc.listen(5)
        print "Serving on %s:%d."%(host, port) # debug
                
        while 1:
            thread.start_new_thread(self.handler_t, soc.accept()+(timeout,))
